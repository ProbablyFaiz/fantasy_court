"""
Create Fantasy Court segment records by analyzing podcast episodes with GPT-5-mini.

This script identifies Fantasy Court segments within podcast episodes from "The Ringer Fantasy
Football Show". Fantasy Court is a recurring segment where the hosts adjudicate fantasy football
disputes and controversies brought by listeners, often featuring humorous debate about league
rules, trade fairness, and player management decisions.

The script uses GPT-5-mini to:
1. Determine if an episode contains a Fantasy Court segment
2. Extract start/end timestamps from episode descriptions (which typically include mm:ss markers)
3. Convert timestamps to seconds for storage
"""

import asyncio

import openai
import rl.utils.click as click
import rl.utils.io
import sqlalchemy as sa
import tqdm
from pydantic import BaseModel, Field
from rich.table import Table
from rl.utils import LOGGER
from sqlalchemy.orm import Session

from court.db.models import FantasyCourtSegment, PodcastEpisode, Provenance
from court.db.session import get_session
from court.utils.print import CONSOLE

_OPENAI_API_KEY = rl.utils.io.getenv("OPENAI_API_KEY")

_DEFAULT_MODEL = "gpt-5-mini"
_DEFAULT_CONCURRENCY = 16
_CREATOR_NAME = "gpt-5-mini"
_TASK_NAME = "create_segments"
_RECORD_TYPE = "fantasy_court_segments"

# System prompt providing context about the podcast and Fantasy Court segment
_SYSTEM_PROMPT = """You are analyzing episodes of "The Ringer Fantasy Football Show", a fantasy football podcast.

"Fantasy Court" is a recurring segment where the hosts (Danny Heifetz, Danny Kelly, Craig Horlbeck)
adjudicate fantasy football disputes and controversies. In this segment:
- Listeners submit grievances about their fantasy leagues (trades, rule disputes, commissioner decisions, etc.)
- The hosts debate and render judgments on these disputes
- It's typically one of the final segments in an episode
- The segment is usually explicitly labeled as "Fantasy Court" in the episode description

Your task is to:
1. Determine if the episode contains a Fantasy Court segment
2. If yes, extract the start timestamp from the description
3. Extract the end timestamp (usually the start of the next segment, or end of show if Fantasy Court is last)

Episode descriptions typically contain timestamps in formats like:
- "32:45" (mm:ss)
- "1:23:45" (hh:mm:ss)

Be precise and only identify segments explicitly labeled as "Fantasy Court" or very clear variations.

If no timestamps are found but the episode contains a Fantasy Court segment, return the start and end timestamps as None.
"""


class FantasyCourtSegmentDetection(BaseModel):
    """Structured output for Fantasy Court segment detection."""

    has_fantasy_court: bool = Field(
        description="Whether this episode contains a Fantasy Court segment"
    )
    start_timestamp: str | None = Field(
        default=None,
        description='Start time in format "(hh:)mm:ss" as found in description, e.g. "45:30" or "1:23:45"',
    )
    end_timestamp: str | None = Field(
        default=None,
        description='End time in format "(hh:)mm:ss" - usually start of next segment or end of show',
    )


def parse_timestamp_to_seconds(timestamp: str) -> float:
    """
    Parse a timestamp string in format (hh:)mm:ss to seconds.

    Args:
        timestamp: Time string like "45:30", "1:23:45", or "32"

    Returns:
        Total seconds as float
    """
    parts = timestamp.strip().split(":")

    if len(parts) == 1:
        # Just seconds: "32"
        return float(parts[0])
    elif len(parts) == 2:
        # mm:ss: "45:30"
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    elif len(parts) == 3:
        # hh:mm:ss: "1:23:45"
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    else:
        raise ValueError(f"Invalid timestamp format: {timestamp}")


def seconds_to_timestamp(seconds: int | float) -> str:
    """
    Convert seconds to (hh:)mm:ss format.

    Args:
        seconds: Total seconds

    Returns:
        Formatted timestamp string
    """
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


async def detect_fantasy_court_segment(
    client: openai.AsyncOpenAI,
    episode: PodcastEpisode,
    model: str,
) -> FantasyCourtSegment | None:
    """
    Use GPT-5-mini to detect Fantasy Court segment in an episode and create segment record.

    Args:
        client: Async OpenAI client
        episode: PodcastEpisode to analyze
        model: OpenAI model to use

    Returns:
        FantasyCourtSegment (without provenance set) if found and valid, None otherwise
    """
    # Format episode duration
    duration_str = (
        seconds_to_timestamp(episode.duration_seconds)
        if episode.duration_seconds
        else "unknown"
    )

    # Prepare user message
    user_message = f"""Episode: {episode.title}
Published: {episode.pub_date.strftime("%B %d, %Y")}
Duration: {duration_str}

Description:
{episode.description or episode.description_html or "No description available"}

Does this episode contain a Fantasy Court segment? If yes, extract the start and end timestamps."""

    # Call GPT-5-mini with structured outputs
    completion = await client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format=FantasyCourtSegmentDetection,
    )

    detection = completion.choices[0].message.parsed

    if not detection.has_fantasy_court:
        return None

    # Parse timestamps to seconds
    if detection.start_timestamp:
        start_seconds = parse_timestamp_to_seconds(detection.start_timestamp)
    else:
        # Shouldn't happen if has_fantasy_court is True, but handle gracefully
        return None

    if detection.end_timestamp:
        end_seconds = parse_timestamp_to_seconds(detection.end_timestamp)
    elif episode.duration_seconds:
        # No end timestamp means segment goes to end of episode
        end_seconds = float(episode.duration_seconds)
    else:
        # Can't determine end time
        return None

    # Validate and cap timestamps
    if start_seconds < 0:
        LOGGER.warning(
            f"Episode {episode.id} has negative start time {start_seconds}s, skipping"
        )
        return None

    if end_seconds < 0:
        LOGGER.warning(
            f"Episode {episode.id} has negative end time {end_seconds}s, skipping"
        )
        return None

    if start_seconds >= end_seconds:
        LOGGER.warning(
            f"Episode {episode.id} has start time {start_seconds}s >= end time {end_seconds}s, skipping"
        )
        return None

    # Cap timestamps to episode duration if available
    if episode.duration_seconds:
        if start_seconds > episode.duration_seconds:
            LOGGER.warning(
                f"Episode {episode.id} start time {start_seconds}s exceeds duration {episode.duration_seconds}s, capping to duration"
            )
            start_seconds = float(episode.duration_seconds)

        if end_seconds > episode.duration_seconds:
            LOGGER.warning(
                f"Episode {episode.id} end time {end_seconds}s exceeds duration {episode.duration_seconds}s, capping to duration"
            )
            end_seconds = float(episode.duration_seconds)

        # Re-check after capping
        if start_seconds >= end_seconds:
            LOGGER.warning(
                f"Episode {episode.id} has invalid segment after capping, skipping"
            )
            return None

    # Create and return segment record (without provenance - caller will set it)
    return FantasyCourtSegment(
        episode_id=episode.id,
        start_time_s=start_seconds,
        end_time_s=end_seconds,
    )


async def process_episodes_batch(
    episodes: list[PodcastEpisode],
    db: Session,
    provenance_id: int,
    model: str,
    concurrency: int,
) -> tuple[int, int]:
    """
    Process a batch of episodes with async concurrency.

    Args:
        episodes: List of episodes to process
        db: Database session
        provenance_id: ID of provenance record
        model: OpenAI model to use
        concurrency: Number of parallel requests

    Returns:
        Tuple of (segments_created, episodes_processed)
    """
    client = openai.AsyncOpenAI(api_key=_OPENAI_API_KEY)
    semaphore = asyncio.Semaphore(concurrency)

    async def process_one(episode: PodcastEpisode) -> FantasyCourtSegment | None:
        async with semaphore:
            try:
                segment = await detect_fantasy_court_segment(client, episode, model)
                if segment:
                    segment.provenance_id = provenance_id
                return segment
            except Exception as e:
                LOGGER.error(
                    f"Error processing episode {episode.id} ({episode.title}): {e}"
                )
                return None

    # Process all episodes concurrently
    tasks = [process_one(ep) for ep in episodes]
    results = []

    # Use tqdm to track progress
    pbar = tqdm.tqdm(total=len(episodes), desc="Processing episodes")
    for coro in asyncio.as_completed(tasks):
        result = await coro
        if result:
            results.append(result)
        pbar.update(1)
    pbar.close()

    # Bulk insert segments
    if results:
        db.add_all(results)
        db.commit()

    return len(results), len(episodes)


@click.command()
@click.option(
    "--model",
    "-m",
    type=str,
    default=_DEFAULT_MODEL,
    help="OpenAI model to use for segment detection",
)
@click.option(
    "--concurrency",
    "-c",
    type=int,
    default=_DEFAULT_CONCURRENCY,
    help="Number of parallel requests to make",
)
def main(model: str, concurrency: int):
    """Detect and create Fantasy Court segment records using GPT-5-mini."""
    CONSOLE.print(
        f"\n[bold blue]Creating Fantasy Court segments using:[/bold blue] {model}"
    )
    CONSOLE.print(f"[bold blue]Concurrency:[/bold blue] {concurrency}\n")

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

        # Get episodes that don't already have segments
        episodes_query = (
            sa.select(PodcastEpisode)
            .outerjoin(FantasyCourtSegment)
            .where(FantasyCourtSegment.id.is_(None))
            .order_by(PodcastEpisode.pub_date)
        )

        episodes = db.execute(episodes_query).scalars().all()

        CONSOLE.print(
            f"[bold]Found {len(episodes)} episodes without Fantasy Court segments[/bold]\n"
        )

        if not episodes:
            CONSOLE.print("[yellow]No episodes to process[/yellow]\n")
            return

        # Process episodes
        segments_created, episodes_processed = asyncio.run(
            process_episodes_batch(episodes, db, provenance.id, model, concurrency)
        )

        CONSOLE.print(
            f"\n[bold green]SUCCESS:[/bold green] Created [bold cyan]{segments_created}[/bold cyan] "
            f"segments from [bold]{episodes_processed}[/bold] episodes processed\n"
        )

        # Display a table with created segments
        if segments_created > 0:
            table = Table(
                title="Sample Created Segments (first 5)",
                show_header=True,
                header_style="bold",
            )
            table.add_column("Episode Title", style="cyan", max_width=40)
            table.add_column("Start", style="green", justify="right")
            table.add_column("End", style="green", justify="right")
            table.add_column("Duration", style="magenta", justify="right")

            # Fetch recently created segments
            recent_segments = (
                db.execute(
                    sa.select(FantasyCourtSegment)
                    .where(FantasyCourtSegment.provenance_id == provenance.id)
                    .order_by(FantasyCourtSegment.created_at.desc())
                    .limit(5)
                )
                .scalars()
                .all()
            )

            for segment in recent_segments:
                episode = db.execute(
                    sa.select(PodcastEpisode).where(
                        PodcastEpisode.id == segment.episode_id
                    )
                ).scalar_one()

                start_str = seconds_to_timestamp(segment.start_time_s)
                end_str = seconds_to_timestamp(segment.end_time_s)
                duration = segment.end_time_s - segment.start_time_s
                duration_str = seconds_to_timestamp(duration)

                table.add_row(episode.title, start_str, end_str, duration_str)

            CONSOLE.print(table)
            CONSOLE.print()
    finally:
        db.close()


if __name__ == "__main__":
    main()
