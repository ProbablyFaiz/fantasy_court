"""CLI commands for Fantasy Court data ingestion operations."""

import rl.utils.click as click

from court.ingest import download_to_bucket, ingest_episodes

_DEFAULT_FEED_URL = "https://feeds.megaphone.fm/ringer-fantasy-football-show"


@click.group()
def ingest():
    """Fantasy Court data ingestion utilities."""
    pass


@ingest.command()
@click.option(
    "--feed-url",
    "-f",
    type=str,
    default=_DEFAULT_FEED_URL,
    help="RSS feed URL to fetch episodes from",
)
def fetch_episodes(feed_url: str):
    """Fetch episodes from RSS feed and populate the podcast_episodes table.

    This command fetches episode metadata from the podcast RSS feed and upserts
    it into the database, creating new episodes or updating existing ones.
    """
    ingest_episodes.main(feed_url)


@ingest.command()
@click.option(
    "--limit",
    "-l",
    type=int,
    default=None,
    help="Maximum number of episodes to download",
)
@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Show what would be downloaded without actually downloading",
)
def download_episodes(limit: int | None, dry_run: bool):
    """Download episode MP3s to S3 bucket for episodes without a bucket path.

    This command downloads MP3 files for episodes that have a canonical MP3 URL
    but no S3 bucket path, uploading them to the configured S3 bucket.
    """
    download_to_bucket.main(limit, dry_run)
