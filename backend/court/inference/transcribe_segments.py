"""
Transcribe Fantasy Court segments using OpenAI's diarization API.

This script:
1. Finds episodes with Fantasy Court segments
2. Extracts the segment audio (with 1-minute buffer on each side)
3. Splits audio into chunks (max 1200 seconds each) if needed
4. Transcribes with speaker diarization using reference samples
5. Combines segments and stores in database
"""

import asyncio
import base64
import tempfile
from pathlib import Path

import openai
import rl.utils.click as click
import rl.utils.io
import sqlalchemy as sa
import tqdm
from openai.types.audio import TranscriptionDiarized
from pydantic import BaseModel
from pydub import AudioSegment
from rich.console import Console
from rich.table import Table
from sqlalchemy.orm import Session, selectinload

from court.db.models import (
    EpisodeTranscript,
    FantasyCourtSegment,
    PodcastEpisode,
    Provenance,
)
from court.db.session import get_session
from court.utils import bucket

_OPENAI_API_KEY = rl.utils.io.getenv("OPENAI_API_KEY")

_DEFAULT_MODEL = "gpt-4o-transcribe-diarize"
_DEFAULT_CONCURRENCY = 8
_CREATOR_NAME = "gpt-4o-transcribe-diarize"
_TASK_NAME = "transcribe_segments"
_RECORD_TYPE = "episode_transcripts"

SPEAKER_SAMPLES_DIR = Path(__file__).parent / "speaker_samples"
MAX_CHUNK_DURATION_SECONDS = 1200  # OpenAI limit is 1400s, use 1200s for safety
SEGMENT_BUFFER_SECONDS = 60  # Add 1 minute buffer on each side

_SPEAKER_NAMES = [
    {"name": "Craig Horlbeck", "file_name": "Craig.wav"},
    {"name": "Danny Kelly", "file_name": "DK.wav"},
    {"name": "Danny Heifetz", "file_name": "Heifetz.wav"},
]


class AudioChunk(BaseModel):
    """Represents an audio chunk file with its duration."""

    path: Path
    duration_seconds: float


def to_data_url(path: Path) -> str:
    """Convert a file to a data URL for use with OpenAI API."""
    with path.open("rb") as fh:
        return "data:audio/wav;base64," + base64.b64encode(fh.read()).decode("utf-8")


def split_mp3_by_duration(
    mp3_data: bytes, max_duration_seconds: int = MAX_CHUNK_DURATION_SECONDS
) -> list[AudioChunk]:
    """
    Split an MP3 file into multiple temporary files, each under max_duration_seconds.

    Returns:
        List of AudioChunk objects with path and duration
    """
    # Load the audio data
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".mp3", delete=False
    ) as tmp_input:
        tmp_input.write(mp3_data)
        tmp_input_path = Path(tmp_input.name)

    audio = AudioSegment.from_mp3(tmp_input_path)
    tmp_input_path.unlink()  # Clean up input temp file

    total_duration_ms = len(audio)
    max_duration_ms = max_duration_seconds * 1000

    # If the original is already short enough, just return it as a single chunk
    if total_duration_ms <= max_duration_ms:
        tmp_file = tempfile.NamedTemporaryFile(mode="wb", suffix=".mp3", delete=False)
        tmp_file.write(mp3_data)
        tmp_file.close()
        return [
            AudioChunk(
                path=Path(tmp_file.name), duration_seconds=total_duration_ms / 1000.0
            )
        ]

    # Split into chunks
    chunks = []
    start_ms = 0

    while start_ms < total_duration_ms:
        end_ms = min(start_ms + max_duration_ms, total_duration_ms)
        chunk = audio[start_ms:end_ms]
        chunk_duration_ms = len(chunk)

        # Export chunk to temp file
        tmp_file = tempfile.NamedTemporaryFile(mode="wb", suffix=".mp3", delete=False)
        chunk.export(tmp_file.name, format="mp3")
        tmp_file.close()
        chunks.append(
            AudioChunk(
                path=Path(tmp_file.name), duration_seconds=chunk_duration_ms / 1000.0
            )
        )

        start_ms = end_ms

    return chunks


def extract_segment_audio(
    full_mp3_data: bytes,
    start_time_s: float,
    end_time_s: float,
    buffer_seconds: int = SEGMENT_BUFFER_SECONDS,
) -> bytes:
    """
    Extract a segment from full episode audio with buffer on each side.

    Args:
        full_mp3_data: Full episode MP3 data
        start_time_s: Segment start time in seconds
        end_time_s: Segment end time in seconds
        buffer_seconds: Buffer to add on each side in seconds

    Returns:
        MP3 data for the segment with buffer
    """
    # Load the audio data
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".mp3", delete=False
    ) as tmp_input:
        tmp_input.write(full_mp3_data)
        tmp_input_path = Path(tmp_input.name)

    audio = AudioSegment.from_mp3(tmp_input_path)
    tmp_input_path.unlink()

    # Calculate start/end with buffer (clamped to audio bounds)
    start_ms = max(0, int((start_time_s - buffer_seconds) * 1000))
    end_ms = min(len(audio), int((end_time_s + buffer_seconds) * 1000))

    # Extract segment
    segment = audio[start_ms:end_ms]

    # Export to bytes
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".mp3", delete=False
    ) as tmp_output:
        segment.export(tmp_output.name, format="mp3")
        tmp_output_path = Path(tmp_output.name)

    segment_data = tmp_output_path.read_bytes()
    tmp_output_path.unlink()

    return segment_data


def print_dry_run_table(segments: list[FantasyCourtSegment], console: Console) -> None:
    """Print a table showing what segments would be transcribed in dry run mode."""
    table = Table(
        title="Segments to Transcribe (Dry Run)",
        show_header=True,
        header_style="bold",
    )
    table.add_column("Episode", style="cyan", max_width=40)
    table.add_column("Start", style="green", justify="right")
    table.add_column("End", style="green", justify="right")
    table.add_column("Duration", style="magenta", justify="right")

    for segment in segments[:10]:
        start = f"{segment.start_time_s:.1f}s"
        end = f"{segment.end_time_s:.1f}s"
        duration = f"{segment.end_time_s - segment.start_time_s:.1f}s"
        table.add_row(segment.episode.title, start, end, duration)

    if len(segments) > 10:
        table.add_row(
            "...",
            "...",
            "...",
            f"... and {len(segments) - 10} more",
        )

    console.print(table)
    console.print()


def print_transcripts_table(
    db: Session, provenance_id: int, console: Console, limit: int = 3
) -> None:
    """Print a table showing recently created transcripts."""
    recent_transcripts = (
        db.execute(
            sa.select(EpisodeTranscript)
            .options(selectinload(EpisodeTranscript.episode))
            .where(EpisodeTranscript.provenance_id == provenance_id)
            .order_by(EpisodeTranscript.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )

    if not recent_transcripts:
        return

    table = Table(
        title=f"Sample Transcripts (first {limit})",
        show_header=True,
        header_style="bold",
    )
    table.add_column("Episode Title", style="cyan", max_width=40)
    table.add_column("Segments", style="green", justify="right")
    table.add_column("Start", style="magenta", justify="right")
    table.add_column("End", style="magenta", justify="right")

    for transcript in recent_transcripts:
        num_segments = len(transcript.transcript_json.get("segments", []))
        start = f"{transcript.transcript_json.get('start_time_s', 0):.1f}s"
        end = f"{transcript.transcript_json.get('end_time_s', 0):.1f}s"

        table.add_row(transcript.episode.title, str(num_segments), start, end)

    console.print(table)
    console.print()


async def transcribe_segment(
    client: openai.AsyncOpenAI,
    segment: FantasyCourtSegment,
    s3_client: bucket.boto3.client,
    speaker_names: list[dict[str, str]],
    speaker_references: list[str],
    console: Console,
) -> dict | None:
    """
    Transcribe a Fantasy Court segment with diarization.

    Args:
        client: Async OpenAI client
        segment: FantasyCourtSegment to transcribe (with episode eager-loaded)
        s3_client: S3 client for bucket operations
        speaker_names: List of speaker name dicts
        speaker_references: List of speaker reference data URLs
        console: Rich console for output

    Returns:
        Combined transcript as dict, or None on error
    """
    import time

    try:
        episode = segment.episode

        # Load MP3 from bucket
        if not episode.bucket_mp3_path:
            console.print(
                f"[yellow]Warning:[/yellow] Episode {episode.id} has no bucket path, skipping"
            )
            return None

        full_mp3_data = bucket.read_file(episode.bucket_mp3_path, s3_client)

        # Extract segment with buffer
        if segment.start_time_s is None or segment.end_time_s is None:
            console.print(
                f"[yellow]Warning:[/yellow] Segment {segment.id} has no start or end time, skipping"
            )
            return None

        # Segmentation and chunking stage
        console.print(
            f"[cyan]Segmenting and chunking:[/cyan] Episode {episode.id} '{episode.title[:40]}...'"
        )
        segment_start = time.time()

        segment_mp3_data = extract_segment_audio(
            full_mp3_data, segment.start_time_s, segment.end_time_s
        )
        chunks = split_mp3_by_duration(segment_mp3_data)

        segment_elapsed = time.time() - segment_start
        console.print(
            f"[green]Segmentation complete:[/green] {len(chunks)} chunk(s) created in {segment_elapsed:.1f}s"
        )

        # Transcription stage
        console.print(
            f"[cyan]Transcribing:[/cyan] {len(chunks)} chunk(s) for episode {episode.id}"
        )
        transcribe_start = time.time()

        all_segments = []
        cumulative_time_offset = 0.0

        for i, chunk in enumerate(chunks, 1):
            chunk_start = time.time()
            with chunk.path.open("rb") as audio_file:
                transcript: TranscriptionDiarized = (
                    await client.audio.transcriptions.create(
                        model="gpt-4o-transcribe-diarize",
                        file=audio_file,
                        response_format="diarized_json",
                        chunking_strategy="auto",
                        extra_body={
                            "known_speaker_names": [s["name"] for s in speaker_names],
                            "known_speaker_references": speaker_references,
                        },
                    )
                )
            chunk_elapsed = time.time() - chunk_start

            # Adjust timestamps for chunks after the first
            for seg in transcript.segments:
                segment_dict = {
                    "id": seg.id,
                    "start": seg.start + cumulative_time_offset,
                    "end": seg.end + cumulative_time_offset,
                    "speaker": seg.speaker,
                    "text": seg.text,
                    "type": seg.type,
                }
                all_segments.append(segment_dict)

            # Update offset based on actual chunk duration
            cumulative_time_offset += chunk.duration_seconds

            console.print(
                f"[dim]  Chunk {i}/{len(chunks)}: {len(transcript.segments)} segments in {chunk_elapsed:.1f}s[/dim]"
            )

        transcribe_elapsed = time.time() - transcribe_start
        console.print(
            f"[green]Transcription complete:[/green] {len(all_segments)} total segments in {transcribe_elapsed:.1f}s"
        )

        # Clean up temp files
        for chunk in chunks:
            chunk.path.unlink()

        # Combine into final transcript structure
        combined_transcript = {
            "segments": all_segments,
            "start_time_s": segment.start_time_s,
            "end_time_s": segment.end_time_s,
        }

        return combined_transcript

    except Exception as e:
        console.print(
            f"[red]Error transcribing segment {segment.id} (episode {episode.id}):[/red] {e}"
        )
        return None


async def process_segments_batch(
    segments: list[FantasyCourtSegment],
    db: Session,
    provenance_id: int,
    concurrency: int,
    console: Console,
    commit_batch_size: int = 16,
) -> tuple[int, int]:
    """
    Process a batch of segments with async concurrency.

    Args:
        segments: List of FantasyCourtSegment (with episodes eager-loaded)
        db: Database session
        provenance_id: ID of provenance record
        concurrency: Number of parallel requests
        console: Rich console for output
        commit_batch_size: Number of transcripts to commit at once

    Returns:
        Tuple of (transcripts_created, segments_processed)
    """
    client = openai.AsyncOpenAI(api_key=_OPENAI_API_KEY)
    s3_client = bucket.get_bucket_client()
    semaphore = asyncio.Semaphore(concurrency)

    # Load speaker references once
    speaker_references = [
        to_data_url(SPEAKER_SAMPLES_DIR / speaker["file_name"])
        for speaker in _SPEAKER_NAMES
    ]

    async def process_one(segment: FantasyCourtSegment) -> EpisodeTranscript | None:
        async with semaphore:
            transcript_data = await transcribe_segment(
                client,
                segment,
                s3_client,
                _SPEAKER_NAMES,
                speaker_references,
                console,
            )

            if not transcript_data:
                return None

            # Create transcript record
            transcript_record = EpisodeTranscript(
                episode_id=segment.episode.id,
                segment_id=segment.id,
                transcript_json=transcript_data,
                provenance_id=provenance_id,
            )

            return transcript_record

    # Process all segments concurrently, committing in batches
    tasks = [process_one(seg) for seg in segments]
    total_created = 0
    pending_commits = []

    # Use tqdm to track progress
    pbar = tqdm.tqdm(total=len(segments), desc="Transcribing segments")
    for coro in asyncio.as_completed(tasks):
        result = await coro
        if result:
            pending_commits.append(result)

            # Commit when batch is full
            if len(pending_commits) >= commit_batch_size:
                db.add_all(pending_commits)
                db.commit()
                total_created += len(pending_commits)
                pending_commits = []

        pbar.update(1)
    pbar.close()

    # Commit any remaining transcripts
    if pending_commits:
        db.add_all(pending_commits)
        db.commit()
        total_created += len(pending_commits)

    return total_created, len(segments)


@click.command()
@click.option(
    "--concurrency",
    "-c",
    type=int,
    default=_DEFAULT_CONCURRENCY,
    help="Number of parallel transcription requests",
)
@click.option(
    "--limit",
    "-l",
    type=int,
    default=None,
    help="Maximum number of segments to transcribe",
)
@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Show what would be transcribed without actually transcribing",
)
def main(concurrency: int, limit: int | None, dry_run: bool):
    """Transcribe Fantasy Court segments using OpenAI's diarization API."""
    console = Console()

    console.print(
        f"\n[bold blue]Transcribing Fantasy Court segments using:[/bold blue] {_DEFAULT_MODEL}"
    )
    console.print(f"[bold blue]Concurrency:[/bold blue] {concurrency}")
    if dry_run:
        console.print("[bold yellow]DRY RUN MODE[/bold yellow]")
    console.print()

    db = get_session()

    try:
        # Create or get provenance record
        provenance = db.execute(
            sa.select(Provenance).where(
                Provenance.task_name == _TASK_NAME,
                Provenance.creator_name == _CREATOR_NAME,
                Provenance.record_type == _RECORD_TYPE,
            )
        ).scalar_one_or_none()

        if not provenance:
            provenance = Provenance(
                task_name=_TASK_NAME,
                creator_name=_CREATOR_NAME,
                record_type=_RECORD_TYPE,
            )
            db.add(provenance)
            db.commit()
            db.refresh(provenance)

        # Get segments that don't already have transcripts
        segments_query = (
            sa.select(FantasyCourtSegment)
            .options(selectinload(FantasyCourtSegment.episode))
            .outerjoin(
                EpisodeTranscript,
                sa.and_(
                    EpisodeTranscript.segment_id == FantasyCourtSegment.id,
                    EpisodeTranscript.provenance_id == provenance.id,
                ),
            )
            .join(PodcastEpisode, FantasyCourtSegment.episode_id == PodcastEpisode.id)
            .where(
                EpisodeTranscript.id.is_(None),
                PodcastEpisode.bucket_mp3_path.isnot(None),
                FantasyCourtSegment.start_time_s.isnot(None),
                FantasyCourtSegment.end_time_s.isnot(None),
            )
            .order_by(PodcastEpisode.pub_date.desc())
        )

        if limit:
            segments_query = segments_query.limit(limit)

        segments = db.execute(segments_query).scalars().all()

        console.print(f"[bold]Found {len(segments)} segments to transcribe[/bold]\n")

        if not segments:
            console.print("[yellow]No segments to transcribe[/yellow]\n")
            return

        # Display dry run table
        if dry_run:
            print_dry_run_table(segments, console)
            return

        # Process segments
        transcripts_created, segments_processed = asyncio.run(
            process_segments_batch(
                segments,
                db,
                provenance.id,
                concurrency,
                console,
            )
        )

        console.print(
            f"\n[bold green]SUCCESS:[/bold green] Created [bold cyan]{transcripts_created}[/bold cyan] "
            f"transcripts from [bold]{segments_processed}[/bold] segments processed\n"
        )

        # Display a table with created transcripts
        if transcripts_created > 0:
            print_transcripts_table(db, provenance.id, console)

    finally:
        db.close()


if __name__ == "__main__":
    main()
