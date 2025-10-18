import datetime
from email.utils import parsedate_to_datetime

import bs4
import httpx
import rl.utils.click as click
import sqlalchemy as sa
from pydantic import BaseModel
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from court.db.models import PodcastEpisode
from court.db.session import get_session

_DEFAULT_FEED_URL = "https://feeds.megaphone.fm/ringer-fantasy-football-show"


class ParsedEpisode(BaseModel):
    """Parsed episode data from RSS feed."""

    guid: str
    title: str
    description: str | None
    description_html: str | None
    pub_date: datetime.datetime | None
    duration_seconds: int | None
    canonical_mp3_url: str | None
    rss_feed_url: str


def parse_rss_feed(feed_url: str) -> list[ParsedEpisode]:
    """Fetch and parse RSS feed, returning a list of parsed episodes."""
    response = httpx.get(feed_url, timeout=30.0)
    response.raise_for_status()

    soup = bs4.BeautifulSoup(response.content, "lxml-xml")
    items = soup.find_all("item")

    episodes = []
    for item in items:
        # Extract basic fields
        guid = item.find("guid")
        guid_text = guid.get_text(strip=True) if guid else None

        title = item.find("title")
        title_text = title.get_text(strip=True) if title else None

        description = item.find("description")
        description_text = description.get_text(strip=True) if description else None

        # Get HTML description from content:encoded
        content_encoded = item.find("content:encoded")
        description_html = None
        if content_encoded:
            description_html = content_encoded.get_text(strip=True)

        # Parse publication date
        pub_date = item.find("pubDate")
        pub_date_dt = None
        if pub_date:
            pub_date_dt = parsedate_to_datetime(pub_date.get_text(strip=True))

        # Get duration in seconds
        duration = item.find("itunes:duration")
        duration_seconds = None
        if duration:
            duration_text = duration.get_text(strip=True)
            try:
                duration_seconds = int(duration_text)
            except ValueError:
                # Sometimes duration is in HH:MM:SS format
                pass

        # Get MP3 URL from enclosure
        enclosure = item.find("enclosure")
        mp3_url = None
        if enclosure:
            mp3_url = enclosure.get("url")

        episodes.append(
            ParsedEpisode(
                guid=guid_text,
                title=title_text,
                description=description_text,
                description_html=description_html,
                pub_date=pub_date_dt,
                duration_seconds=duration_seconds,
                canonical_mp3_url=mp3_url,
                rss_feed_url=feed_url,
            )
        )

    return episodes


def upsert_episodes(
    db: sa.orm.Session, episodes: list[ParsedEpisode], console: Console
) -> tuple[int, int]:
    """
    Upsert episodes into the database.

    Returns:
        Tuple of (inserted_count, updated_count)
    """
    # Fetch all existing episodes by guid in a single query
    guids = [ep.guid for ep in episodes]
    existing_episodes = (
        db.execute(sa.select(PodcastEpisode).where(PodcastEpisode.guid.in_(guids)))
        .scalars()
        .all()
    )

    # Create a mapping of guid -> episode for fast lookup
    existing_by_guid = {ep.guid: ep for ep in existing_episodes}

    inserted = 0
    updated = 0

    with Progress(console=console) as progress:
        task = progress.add_task("Upserting episodes", total=len(episodes))

        for parsed_episode in episodes:
            existing = existing_by_guid.get(parsed_episode.guid)

            if existing:
                # Update existing episode
                for key, value in parsed_episode.model_dump().items():
                    if key != "guid":  # Don't update the guid
                        setattr(existing, key, value)
                updated += 1
            else:
                # Insert new episode
                new_episode = PodcastEpisode(**parsed_episode.model_dump())
                db.add(new_episode)
                inserted += 1

            progress.advance(task)

    db.commit()
    return inserted, updated


@click.command()
@click.option(
    "--feed-url",
    "-f",
    type=str,
    default=_DEFAULT_FEED_URL,
    help="RSS feed URL to fetch episodes from",
)
def main(feed_url: str):
    """Fetch episodes from RSS feed and populate the podcast_episodes table."""
    console = Console()

    console.print(f"\n[bold blue]Fetching episodes from:[/bold blue] {feed_url}")

    episodes = parse_rss_feed(feed_url)
    console.print(
        f"[bold green]SUCCESS:[/bold green] Parsed [bold]{len(episodes)}[/bold] episodes from RSS feed\n"
    )

    db = get_session()
    try:
        inserted, updated = upsert_episodes(db, episodes, console)
        console.print(
            f"\n[bold green]SUCCESS:[/bold green] Upserted episodes: "
            f"[bold cyan]{inserted}[/bold cyan] inserted, "
            f"[bold yellow]{updated}[/bold yellow] updated\n"
        )

        # Display a table with the first 3 episodes
        table = Table(title="First 3 Episodes", show_header=True, header_style="bold")
        table.add_column("Title", style="cyan", max_width=50)
        table.add_column("Pub Date", style="magenta")
        table.add_column("Duration", style="green", justify="right")

        # Fetch the 3 most recent episodes
        recent_episodes = (
            db.execute(
                sa.select(PodcastEpisode)
                .order_by(PodcastEpisode.pub_date.desc())
                .limit(3)
            )
            .scalars()
            .all()
        )

        for episode in recent_episodes:
            duration_str = (
                f"{episode.duration_seconds // 60}m {episode.duration_seconds % 60}s"
                if episode.duration_seconds
                else "N/A"
            )
            pub_date_str = (
                episode.pub_date.strftime("%Y-%m-%d") if episode.pub_date else "N/A"
            )
            table.add_row(episode.title, pub_date_str, duration_str)

        console.print(table)
        console.print()
    finally:
        db.close()


if __name__ == "__main__":
    main()
