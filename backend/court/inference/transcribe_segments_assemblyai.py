"""
Transcribe Fantasy Court segments using AssemblyAI's API with speaker identification.

This script:
1. Finds episodes with Fantasy Court segments
2. Creates presigned URLs for episode audio with time-based slicing
3. Transcribes with speaker diarization using slam-1 model
4. Identifies speaker names using LeMUR (Danny Heifetz, Danny Kelly, Craig Horlbeck, and guests)
5. Stores transcripts with identified speakers in database
"""

import asyncio
import json
import re

import assemblyai as aai
import rl.utils.click as click
import rl.utils.io
import sqlalchemy as sa
import tqdm
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
from court.utils.print import CONSOLE

_ASSEMBLYAI_API_KEY = rl.utils.io.getenv("ASSEMBLYAI_API_KEY")

_DEFAULT_CONCURRENCY = 8
_CREATOR_NAME = "assemblyai"
_TASK_NAME = "transcribe_segments"
_RECORD_TYPE = "episode_transcripts"

SEGMENT_BUFFER_SECONDS = (
    300  # Add 5 minutes buffer on each side as timestamps are often inaccurate
)
EXPECTED_SPEAKERS = 3  # Craig Horlbeck, Danny Kelly, Danny Heifetz


def print_dry_run_table(segments: list[FantasyCourtSegment]) -> None:
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

    CONSOLE.print(table)
    CONSOLE.print()


def print_transcripts_table(db: Session, provenance_id: int, limit: int = 3) -> None:
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
        start = f"{transcript.start_time_s:.1f}s"
        end = f"{transcript.end_time_s:.1f}s"

        table.add_row(transcript.episode.title, str(num_segments), start, end)

    CONSOLE.print(table)
    CONSOLE.print()


async def identify_speakers_with_lemur(
    utterances: list[aai.Utterance],
) -> dict[str, str]:
    """
    Identify speaker names from transcript utterances using LeMUR.

    Args:
        utterances: List of AssemblyAI utterances with speaker labels

    Returns:
        Dictionary mapping speaker labels (e.g., 'A', 'B') to speaker names
    """
    import time

    lemur_start = time.time()
    CONSOLE.print("[cyan]Identifying speakers with LeMUR...[/cyan]")

    # Create speaker-labeled text for LeMUR
    text_with_speaker_labels = ""
    for utt in utterances:
        text_with_speaker_labels += f"Speaker {utt.speaker}:\n{utt.text}\n"

    # Get unique speakers for the prompt
    unique_speakers = {utt.speaker for utt in utterances}
    speakers_list = ", ".join(f"Speaker {s}" for s in sorted(unique_speakers))

    # Query LeMUR with a single request for all speakers
    lemur_context = (
        "This is a transcript from The Ringer Fantasy Football Show. "
        "The regular hosts are Danny Heifetz (often referred to as just 'Heifetz'), "
        "Danny Kelly (usually called 'DK'), and Craig Horlbeck. "
        "Sometimes there are guest appearances by other people. "
        f"Identify all speakers ({speakers_list}) from the transcript and return a JSON object "
        "mapping each speaker label to their name. "
        "If a speaker is a guest and not one of the regular hosts, extract and identify their name if mentioned."
    )

    result = await aai.Lemur().task_async(
        "Identify all speakers in this transcript and return a JSON object mapping speaker labels to names. "
        "Format: {'A': 'Full Name', 'B': 'Full Name', ...}",
        input_text=text_with_speaker_labels,
        final_model=aai.LemurModel.claude_sonnet_4_20250514,
        context=lemur_context,
    )

    # Parse JSON response
    speaker_mapping = {}
    try:
        speaker_mapping = json.loads(result.response)
    except json.JSONDecodeError:
        # Fallback: try to extract JSON from response text
        json_match = re.search(r"\{[^}]+\}", result.response)
        if json_match:
            speaker_mapping = json.loads(json_match.group(0))
        else:
            CONSOLE.print(
                "[yellow]Warning: Could not parse LeMUR response as JSON, using fallback[/yellow]"
            )

    lemur_elapsed = time.time() - lemur_start
    CONSOLE.print(
        f"[green]Speaker identification complete:[/green] {len(speaker_mapping)} speakers in {lemur_elapsed:.1f}s"
    )
    CONSOLE.print(f"[dim]  Identified: {speaker_mapping}[/dim]")

    return speaker_mapping


async def transcribe_segment(
    segment: FantasyCourtSegment,
    s3_client: bucket.boto3.client,
) -> dict | None:
    """
    Transcribe a Fantasy Court segment using AssemblyAI with speaker identification.

    Args:
        segment: FantasyCourtSegment to transcribe (with episode eager-loaded)
        s3_client: S3 client for bucket operations

    Returns:
        Transcript as dict with identified speaker names, or None on error
    """
    import time

    try:
        episode = segment.episode

        if not episode.bucket_mp3_path:
            CONSOLE.print(
                f"[yellow]Warning:[/yellow] Episode {episode.id} has no bucket path, skipping"
            )
            return None

        if segment.start_time_s is None or segment.end_time_s is None:
            CONSOLE.print(
                f"[yellow]Warning:[/yellow] Segment {segment.id} has no start or end time, skipping"
            )
            return None

        # Calculate time range with buffer (in milliseconds for AssemblyAI)
        episode_duration = (
            episode.duration_seconds if episode.duration_seconds else "unknown"
        )
        segment_duration = segment.end_time_s - segment.start_time_s

        # Apply buffer and clamp to episode bounds
        actual_start_s = max(0, segment.start_time_s - SEGMENT_BUFFER_SECONDS)
        actual_end_s = segment.end_time_s + SEGMENT_BUFFER_SECONDS
        if episode.duration_seconds:
            actual_end_s = min(actual_end_s, episode.duration_seconds)

        # Convert to milliseconds for AssemblyAI
        audio_start_from_ms = int(actual_start_s * 1000)
        audio_end_at_ms = int(actual_end_s * 1000)

        CONSOLE.print(
            f"[cyan]Transcribing:[/cyan] Episode {episode.id} '{episode.title[:40]}...' "
            f"(episode: {episode_duration}s, segment: {segment_duration:.1f}s, range: {actual_start_s:.1f}s-{actual_end_s:.1f}s)"
        )

        # Create presigned URL for full episode audio
        audio_url = bucket.get_signed_url(episode.bucket_mp3_path, s3_client)

        transcribe_start = time.time()

        # Configure transcriber with speaker labels and slam-1 model
        config = aai.TranscriptionConfig(
            speaker_labels=True,
            speakers_expected=EXPECTED_SPEAKERS,
            audio_start_from=audio_start_from_ms,
            audio_end_at=audio_end_at_ms,
            speech_model=aai.SpeechModel.slam_1,
        )
        transcriber = aai.Transcriber(config=config)

        # Use async transcription
        transcript: aai.Transcript = await transcriber.transcribe_async(audio_url)

        if transcript.status == aai.TranscriptStatus.error:
            raise Exception(f"Transcription failed: {transcript.error}")

        transcribe_elapsed = time.time() - transcribe_start
        CONSOLE.print(
            f"[green]Transcription complete:[/green] {len(transcript.utterances or [])} utterances in {transcribe_elapsed:.1f}s"
        )

        # Identify speakers using LeMUR
        speaker_mapping = {}
        if transcript.utterances:
            speaker_mapping = await identify_speakers_with_lemur(transcript.utterances)

        # Convert AssemblyAI format to our format with identified names
        segments = []
        if transcript.utterances:
            for utterance in transcript.utterances:
                speaker_name = speaker_mapping.get(
                    utterance.speaker, f"Speaker {utterance.speaker}"
                )
                segments.append(
                    {
                        "id": len(segments),
                        "start": utterance.start / 1000.0,  # Convert ms to seconds
                        "end": utterance.end / 1000.0,
                        "speaker": speaker_name,
                        "text": utterance.text,
                        "type": "utterance",
                    }
                )

        combined_transcript = {
            "segments": segments,
            "actual_start_s": actual_start_s,
            "actual_end_s": actual_end_s,
        }

        return combined_transcript

    except Exception as e:
        CONSOLE.print(
            f"[red]Error transcribing segment {segment.id} (episode {episode.id}):[/red] {e}"
        )
        return None


async def process_segments_batch(
    segments: list[FantasyCourtSegment],
    db: Session,
    provenance_id: int,
    concurrency: int,
    commit_batch_size: int = 16,
) -> tuple[int, int]:
    """
    Process a batch of segments with async concurrency.

    Args:
        segments: List of FantasyCourtSegment (with episodes eager-loaded)
        db: Database session
        provenance_id: ID of provenance record
        concurrency: Number of parallel requests
        commit_batch_size: Number of transcripts to commit at once

    Returns:
        Tuple of (transcripts_created, segments_processed)
    """
    s3_client = bucket.get_bucket_client()
    semaphore = asyncio.Semaphore(concurrency)

    async def process_one(segment: FantasyCourtSegment) -> EpisodeTranscript | None:
        async with semaphore:
            transcript_data = await transcribe_segment(segment, s3_client)

            if not transcript_data:
                return None

            # Extract metadata from transcript data
            actual_start_s = transcript_data.pop("actual_start_s")
            actual_end_s = transcript_data.pop("actual_end_s")

            # Create transcript record with start/end as columns
            transcript_record = EpisodeTranscript(
                episode_id=segment.episode.id,
                segment_id=segment.id,
                transcript_json=transcript_data,  # Only contains segments now
                start_time_s=actual_start_s,
                end_time_s=actual_end_s,
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
    """Transcribe Fantasy Court segments using AssemblyAI's API."""
    # Initialize AssemblyAI settings
    aai.settings.api_key = _ASSEMBLYAI_API_KEY

    CONSOLE.print(
        "\n[bold blue]Transcribing Fantasy Court segments using:[/bold blue] AssemblyAI"
    )
    CONSOLE.print(f"[bold blue]Concurrency:[/bold blue] {concurrency}")
    if dry_run:
        CONSOLE.print("[bold yellow]DRY RUN MODE[/bold yellow]")
    CONSOLE.print()

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

        CONSOLE.print(f"[bold]Found {len(segments)} segments to transcribe[/bold]\n")

        if not segments:
            CONSOLE.print("[yellow]No segments to transcribe[/yellow]\n")
            return

        # Display dry run table
        if dry_run:
            print_dry_run_table(segments)
            return

        # Process segments
        transcripts_created, segments_processed = asyncio.run(
            process_segments_batch(
                segments,
                db,
                provenance.id,
                concurrency,
            )
        )

        CONSOLE.print(
            f"\n[bold green]SUCCESS:[/bold green] Created [bold cyan]{transcripts_created}[/bold cyan] "
            f"transcripts from [bold]{segments_processed}[/bold] segments processed\n"
        )

        # Display a table with created transcripts
        if transcripts_created > 0:
            print_transcripts_table(db, provenance.id)

    finally:
        db.close()


if __name__ == "__main__":
    main()
