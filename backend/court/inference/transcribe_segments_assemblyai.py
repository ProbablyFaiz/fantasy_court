"""
Transcribe Fantasy Court segments using AssemblyAI with speaker identification.

This script:
1. Finds Fantasy Court segments that do not yet have a transcript
2. Creates a presigned URL for the episode audio and asks AssemblyAI to transcribe
   only the segment's time range (plus a buffer on each side)
3. Transcribes with Universal-3.5 Pro and speaker diarization
4. Names speakers with AssemblyAI's Speaker Identification (no voice samples needed)
5. Stores transcripts with episode-relative timestamps in the database
"""

import asyncio
import time

import assemblyai as aai
import rl.utils.click as click
import rl.utils.io
import sqlalchemy as sa
import tqdm
from assemblyai.prerecorded.v2 import AsyncTranscriber, TranscriptionConfig
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

_DEFAULT_MODEL = "universal-3-5-pro"
_DEFAULT_CONCURRENCY = 8
_CREATOR_NAME = "assemblyai-universal-3-5-pro"
_TASK_NAME = "transcribe_segments"
_RECORD_TYPE = "episode_transcripts"

SEGMENT_BUFFER_SECONDS = (
    300  # Add 5 minutes buffer on each side as timestamps are often inaccurate
)
# Three regular hosts, with headroom for the occasional guest. A hard exact count
# hurts diarization accuracy when a guest is present, so use a range instead.
MIN_SPEAKERS = 2
MAX_SPEAKERS = 5

KNOWN_SPEAKERS: list[dict[str, str]] = [
    {
        "name": "Danny Heifetz",
        "description": (
            "Host of The Ringer Fantasy Football Show. Often referred to as just "
            "'Heifetz'. Frequently presides over Fantasy Court as the judge."
        ),
    },
    {
        "name": "Danny Kelly",
        "description": (
            "Host of The Ringer Fantasy Football Show. Usually called 'DK'. "
            "Argues cases in Fantasy Court."
        ),
    },
    {
        "name": "Craig Horlbeck",
        "description": (
            "Host of The Ringer Fantasy Football Show. Usually called 'Craig'. "
            "Argues cases in Fantasy Court and reads listener submissions."
        ),
    },
]


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
        table.add_row("...", "...", "...", f"... and {len(segments) - 10} more")

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
    table.add_column("Utterances", style="green", justify="right")
    table.add_column("Speakers", style="cyan", max_width=40)
    table.add_column("Start", style="magenta", justify="right")
    table.add_column("End", style="magenta", justify="right")

    for transcript in recent_transcripts:
        segments = transcript.transcript_json.get("segments", [])
        speakers = ", ".join(sorted({s["speaker"] for s in segments}))
        table.add_row(
            transcript.episode.title,
            str(len(segments)),
            speakers,
            f"{transcript.start_time_s:.1f}s",
            f"{transcript.end_time_s:.1f}s",
        )

    CONSOLE.print(table)
    CONSOLE.print()


def build_transcription_config(
    model: str, audio_start_from_ms: int, audio_end_at_ms: int
) -> TranscriptionConfig:
    """Build the AssemblyAI request config for one segment."""
    return TranscriptionConfig(
        speech_models=[model],
        audio_start_from=audio_start_from_ms,
        audio_end_at=audio_end_at_ms,
        speaker_labels=True,
        speaker_options=aai.SpeakerOptions(
            min_speakers_expected=MIN_SPEAKERS,
            max_speakers_expected=MAX_SPEAKERS,
        ),
        speech_understanding=aai.SpeechUnderstandingRequest(
            request=aai.SpeechUnderstandingFeatureRequests(
                speaker_identification=aai.SpeakerIdentificationRequest(
                    speaker_type=aai.SpeakerType.name,
                    speakers=KNOWN_SPEAKERS,
                )
            )
        ),
    )


async def transcribe_segment(
    segment: FantasyCourtSegment,
    transcriber: AsyncTranscriber,
    s3_client: bucket.boto3.client,
    model: str,
) -> dict | None:
    """
    Transcribe a Fantasy Court segment using AssemblyAI with speaker identification.

    Args:
        segment: FantasyCourtSegment to transcribe (with episode eager-loaded)
        transcriber: Shared AssemblyAI async transcriber
        s3_client: S3 client for bucket operations
        model: AssemblyAI speech model ID

    Returns:
        Dict with "segments" (episode-relative timestamps and identified speaker
        names) plus "actual_start_s" and "actual_end_s" metadata, or None on error
    """
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

    try:
        # Apply buffer and clamp to episode bounds
        actual_start_s = max(0.0, segment.start_time_s - SEGMENT_BUFFER_SECONDS)
        actual_end_s = segment.end_time_s + SEGMENT_BUFFER_SECONDS
        if episode.duration_seconds:
            actual_end_s = min(actual_end_s, float(episode.duration_seconds))

        CONSOLE.print(
            f"[cyan]Transcribing:[/cyan] Episode {episode.id} '{episode.title[:40]}...' "
            f"(segment: {segment.end_time_s - segment.start_time_s:.1f}s, "
            f"range: {actual_start_s:.1f}s-{actual_end_s:.1f}s)"
        )

        audio_url = bucket.get_signed_url(episode.bucket_mp3_path, s3_client)
        config = build_transcription_config(
            model, int(actual_start_s * 1000), int(actual_end_s * 1000)
        )

        transcribe_start = time.time()
        transcript = await transcriber.transcribe(audio_url, config=config)
        if transcript.status == aai.TranscriptStatus.error:
            raise RuntimeError(f"AssemblyAI transcription failed: {transcript.error}")

        utterances = transcript.utterances or []
        transcribe_elapsed = time.time() - transcribe_start
        speakers = sorted({u.speaker for u in utterances if u.speaker})
        CONSOLE.print(
            f"[green]Transcription complete:[/green] episode {episode.id}, "
            f"{len(utterances)} utterances in {transcribe_elapsed:.1f}s "
            f"(model: {transcript.speech_model_used}, speakers: {', '.join(speakers)})"
        )

        # AssemblyAI keeps timestamps relative to the full file even when
        # audio_start_from is set, so no offset is needed.
        segments = [
            {
                "id": str(i),
                "start": utterance.start / 1000.0,
                "end": utterance.end / 1000.0,
                "speaker": utterance.speaker or "Unknown",
                "text": utterance.text,
                "type": "utterance",
            }
            for i, utterance in enumerate(utterances)
        ]

        return {
            "segments": segments,
            "actual_start_s": actual_start_s,
            "actual_end_s": actual_end_s,
        }

    except Exception as e:
        CONSOLE.print(
            f"[red]Error transcribing segment {segment.id} (episode {episode.id}):[/red] {e}"
        )
        return None


async def process_segments_batch(
    segments: list[FantasyCourtSegment],
    db: Session,
    provenance_id: int,
    model: str,
    concurrency: int,
) -> tuple[int, int]:
    """
    Transcribe segments concurrently, committing each transcript as it lands.

    Returns:
        Tuple of (transcripts_created, segments_processed)
    """
    s3_client = bucket.get_bucket_client()
    semaphore = asyncio.Semaphore(concurrency)
    transcriber = AsyncTranscriber(api_key=_ASSEMBLYAI_API_KEY)

    async def process_one(
        segment: FantasyCourtSegment,
    ) -> tuple[FantasyCourtSegment, dict | None]:
        async with semaphore:
            return segment, await transcribe_segment(
                segment, transcriber, s3_client, model
            )

    total_created = 0
    try:
        pbar = tqdm.tqdm(total=len(segments), desc="Transcribing segments")
        for coro in asyncio.as_completed([process_one(seg) for seg in segments]):
            segment, transcript_data = await coro
            if transcript_data:
                db.add(
                    EpisodeTranscript(
                        episode_id=segment.episode.id,
                        segment_id=segment.id,
                        transcript_json={"segments": transcript_data["segments"]},
                        start_time_s=transcript_data["actual_start_s"],
                        end_time_s=transcript_data["actual_end_s"],
                        provenance_id=provenance_id,
                    )
                )
                db.commit()
                total_created += 1
            pbar.update(1)
        pbar.close()
    finally:
        await transcriber.aclose()

    return total_created, len(segments)


@click.command()
@click.option(
    "--model",
    "-m",
    type=str,
    default=_DEFAULT_MODEL,
    help="AssemblyAI speech model to use",
)
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
def main(model: str, concurrency: int, limit: int | None, dry_run: bool):
    """Transcribe Fantasy Court segments using AssemblyAI with speaker identification."""
    if not _ASSEMBLYAI_API_KEY:
        raise click.ClickException("ASSEMBLYAI_API_KEY is not set")

    CONSOLE.print(
        f"\n[bold blue]Transcribing Fantasy Court segments using:[/bold blue] AssemblyAI {model}"
    )
    CONSOLE.print(f"[bold blue]Concurrency:[/bold blue] {concurrency}")
    if dry_run:
        CONSOLE.print("[bold yellow]DRY RUN MODE[/bold yellow]")
    CONSOLE.print()

    db = get_session()

    try:
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

        # Segments have at most one transcript, so skip any segment that already
        # has one regardless of which transcriber produced it.
        segments_query = (
            sa.select(FantasyCourtSegment)
            .options(selectinload(FantasyCourtSegment.episode))
            .outerjoin(
                EpisodeTranscript,
                EpisodeTranscript.segment_id == FantasyCourtSegment.id,
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

        segments = list(db.execute(segments_query).scalars().all())

        CONSOLE.print(f"[bold]Found {len(segments)} segments to transcribe[/bold]\n")

        if not segments:
            CONSOLE.print("[yellow]No segments to transcribe[/yellow]\n")
            return

        if dry_run:
            print_dry_run_table(segments)
            return

        transcripts_created, segments_processed = asyncio.run(
            process_segments_batch(segments, db, provenance.id, model, concurrency)
        )

        CONSOLE.print(
            f"\n[bold green]SUCCESS:[/bold green] Created [bold cyan]{transcripts_created}[/bold cyan] "
            f"transcripts from [bold]{segments_processed}[/bold] segments processed\n"
        )

        if transcripts_created > 0:
            print_transcripts_table(db, provenance.id)

    finally:
        db.close()


if __name__ == "__main__":
    main()
