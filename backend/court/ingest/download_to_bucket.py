import asyncio
import tempfile
import time
from pathlib import Path

import httpx
import rl.utils.click as click
import sqlalchemy as sa
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from sqlalchemy.orm import Session

from court.db.models import PodcastEpisode
from court.db.session import get_session
from court.utils import bucket
from court.utils.print import CONSOLE

_DEFAULT_CONCURRENCY = 8
_CHUNK_SIZE = 256 * 1024


def generate_bucket_path(episode: PodcastEpisode) -> str:
    """Generate a consistent S3 path for an episode's MP3 file."""
    # Use pub_date for folder structure: episodes/YYYY/MM/guid.mp3
    if episode.pub_date:
        year = episode.pub_date.year
        month = f"{episode.pub_date.month:02d}"
        return f"episodes/{year}/{month}/{episode.guid}.mp3"
    # Fallback to just guid if no pub_date
    return f"episodes/{episode.guid}.mp3"


class _Throughput:
    """Tracks cumulative bytes downloaded across all concurrent streams."""

    def __init__(self) -> None:
        self.start = time.monotonic()
        self.total_bytes = 0

    def add(self, n: int) -> None:
        self.total_bytes += n

    def mb_per_s(self) -> float:
        elapsed = time.monotonic() - self.start
        return self.total_bytes / elapsed / 1e6 if elapsed > 0 else 0.0


async def download_episode_mp3(
    episode: PodcastEpisode,
    http: httpx.AsyncClient,
    s3_client: bucket.boto3.client,
    throughput: _Throughput,
    semaphore: asyncio.Semaphore,
    tmp_dir: Path,
) -> bool:
    """
    Stream an episode's MP3 from its canonical URL to disk, then upload it to S3.

    Returns:
        True if successful, False otherwise
    """
    if not episode.canonical_mp3_url:
        CONSOLE.print(
            f"[yellow]WARNING:[/yellow] Episode '{episode.title}' has no canonical MP3 URL"
        )
        return False

    async with semaphore:
        tmp_path = tmp_dir / f"{episode.guid}.mp3"
        try:
            async with http.stream("GET", episode.canonical_mp3_url) as response:
                response.raise_for_status()
                with tmp_path.open("wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=_CHUNK_SIZE):
                        f.write(chunk)
                        throughput.add(len(chunk))

            await asyncio.to_thread(
                bucket.write_file, tmp_path, generate_bucket_path(episode), s3_client
            )
            return True
        except Exception as e:
            CONSOLE.print(f"[red]ERROR:[/red] Failed to download {episode.title}: {e}")
            return False
        finally:
            tmp_path.unlink(missing_ok=True)


async def _download_all(
    episodes: list[PodcastEpisode],
    db: Session,
    concurrency: int,
) -> tuple[int, int]:
    """Download all episodes concurrently, committing each bucket path as it lands."""
    s3_client = bucket.get_bucket_client()
    semaphore = asyncio.Semaphore(concurrency)
    throughput = _Throughput()
    successful = 0
    failed = 0

    with (
        tempfile.TemporaryDirectory(prefix="court-mp3-") as tmp_dir_str,
        Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TextColumn("[cyan]{task.fields[speed]:.1f} MB/s"),
            console=CONSOLE,
        ) as progress,
    ):
        tmp_dir = Path(tmp_dir_str)
        overall_task = progress.add_task(
            "Downloading episodes", total=len(episodes), speed=0.0
        )

        async def refresh_speed() -> None:
            while True:
                progress.update(overall_task, speed=throughput.mb_per_s())
                await asyncio.sleep(1)

        speed_refresher = asyncio.create_task(refresh_speed())
        try:
            async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as http:

                async def run_one(
                    episode: PodcastEpisode,
                ) -> tuple[PodcastEpisode, bool]:
                    ok = await download_episode_mp3(
                        episode, http, s3_client, throughput, semaphore, tmp_dir
                    )
                    return episode, ok

                for coro in asyncio.as_completed([run_one(ep) for ep in episodes]):
                    episode, ok = await coro
                    if ok:
                        episode.bucket_mp3_path = generate_bucket_path(episode)
                        db.commit()
                        successful += 1
                    else:
                        failed += 1
                    progress.update(
                        overall_task, advance=1, speed=throughput.mb_per_s()
                    )
        finally:
            speed_refresher.cancel()

    return successful, failed


def main(
    limit: int | None = None,
    dry_run: bool = False,
    concurrency: int = _DEFAULT_CONCURRENCY,
):
    """Download episode MP3s to S3 bucket for episodes without a bucket path."""
    CONSOLE.print("\n[bold blue]Fetching episodes without bucket paths...[/bold blue]")

    db = get_session()
    try:
        # Query episodes that don't have a bucket path but do have a canonical URL
        query = sa.select(PodcastEpisode).where(
            PodcastEpisode.bucket_mp3_path.is_(None),
            PodcastEpisode.canonical_mp3_url.isnot(None),
        )

        if limit:
            query = query.limit(limit)

        episodes = list(db.execute(query).scalars().all())

        CONSOLE.print(
            f"[bold green]SUCCESS:[/bold green] Found [bold]{len(episodes)}[/bold] episodes to download\n"
        )

        if len(episodes) == 0:
            CONSOLE.print("[green]No episodes to download![/green]\n")
            return

        if dry_run:
            # Show what would be downloaded
            table = Table(title="Episodes to Download (Dry Run)", show_header=True)
            table.add_column("Title", style="cyan", max_width=50)
            table.add_column("Pub Date", style="magenta")
            table.add_column("S3 Path", style="green", max_width=40)

            for episode in episodes[:10]:  # Show first 10
                pub_date_str = (
                    episode.pub_date.strftime("%Y-%m-%d") if episode.pub_date else "N/A"
                )
                s3_path = generate_bucket_path(episode)
                table.add_row(episode.title, pub_date_str, s3_path)

            if len(episodes) > 10:
                table.add_row("...", "...", f"... and {len(episodes) - 10} more")

            CONSOLE.print(table)
            CONSOLE.print()
            return

        successful, failed = asyncio.run(_download_all(episodes, db, concurrency))

        CONSOLE.print(
            f"\n[bold green]SUCCESS:[/bold green] Download complete: "
            f"[bold cyan]{successful}[/bold cyan] successful, "
            f"[bold red]{failed}[/bold red] failed\n"
        )

        # Display a sample of downloaded episodes
        if successful > 0:
            table = Table(
                title="Sample of Downloaded Episodes",
                show_header=True,
                header_style="bold",
            )
            table.add_column("Title", style="cyan", max_width=50)
            table.add_column("Pub Date", style="magenta")
            table.add_column("Bucket Path", style="green", max_width=40)

            # Get the episodes we just updated
            recent_updated = (
                db.execute(
                    sa.select(PodcastEpisode)
                    .where(PodcastEpisode.bucket_mp3_path.isnot(None))
                    .order_by(PodcastEpisode.created_at.desc())
                    .limit(3)
                )
                .scalars()
                .all()
            )

            for episode in recent_updated:
                pub_date_str = (
                    episode.pub_date.strftime("%Y-%m-%d") if episode.pub_date else "N/A"
                )
                table.add_row(episode.title, pub_date_str, episode.bucket_mp3_path)

            CONSOLE.print(table)
            CONSOLE.print()

    finally:
        db.close()


@click.command()
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
@click.option(
    "--concurrency",
    "-c",
    type=int,
    default=_DEFAULT_CONCURRENCY,
    help="Number of episodes to download in parallel",
)
def cli(limit: int | None, dry_run: bool, concurrency: int):
    """Download episode MP3s to S3 bucket for episodes without a bucket path."""
    main(limit, dry_run, concurrency)


if __name__ == "__main__":
    cli()
