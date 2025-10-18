import httpx
import rl.utils.click as click
import sqlalchemy as sa
from rich.console import Console
from rich.progress import Progress, TaskID
from rich.table import Table

from court.db.models import PodcastEpisode
from court.db.session import get_session
from court.utils import bucket


def generate_bucket_path(episode: PodcastEpisode) -> str:
    """Generate a consistent S3 path for an episode's MP3 file."""
    # Use pub_date for folder structure: episodes/YYYY/MM/guid.mp3
    if episode.pub_date:
        year = episode.pub_date.year
        month = f"{episode.pub_date.month:02d}"
        return f"episodes/{year}/{month}/{episode.guid}.mp3"
    # Fallback to just guid if no pub_date
    return f"episodes/{episode.guid}.mp3"


def download_episode_mp3(
    episode: PodcastEpisode,
    s3_client: bucket.boto3.client,
    console: Console,
    progress: Progress,
    task: TaskID,
) -> bool:
    """
    Download an episode's MP3 from canonical URL and upload to S3.

    Returns:
        True if successful, False otherwise
    """
    if not episode.canonical_mp3_url:
        console.print(
            f"[yellow]WARNING:[/yellow] Episode '{episode.title}' has no canonical MP3 URL"
        )
        return False

    try:
        # Download from canonical URL with streaming
        with httpx.stream(
            "GET", episode.canonical_mp3_url, timeout=300.0, follow_redirects=True
        ) as response:
            response.raise_for_status()

            # Get total size if available
            total_size = int(response.headers.get("content-length", 0))
            chunks = []

            # Download with progress tracking
            download_task = progress.add_task(
                f"Downloading {episode.title[:40]}...",
                total=total_size if total_size > 0 else None,
            )

            for chunk in response.iter_bytes(chunk_size=8192):
                chunks.append(chunk)
                progress.update(download_task, advance=len(chunk))

            progress.remove_task(download_task)
            mp3_data = b"".join(chunks)

        # Generate S3 path and upload
        s3_path = generate_bucket_path(episode)
        bucket.write_file(mp3_data, s3_path, s3_client)

        return True

    except Exception as e:
        console.print(f"[red]ERROR:[/red] Failed to download {episode.title}: {e}")
        return False


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
def main(limit: int | None, dry_run: bool):
    """Download episode MP3s to S3 bucket for episodes without a bucket path."""
    console = Console()

    console.print("\n[bold blue]Fetching episodes without bucket paths...[/bold blue]")

    db = get_session()
    try:
        # Query episodes that don't have a bucket path but do have a canonical URL
        query = sa.select(PodcastEpisode).where(
            PodcastEpisode.bucket_mp3_path.is_(None),
            PodcastEpisode.canonical_mp3_url.isnot(None),
        )

        if limit:
            query = query.limit(limit)

        episodes = db.execute(query).scalars().all()

        console.print(
            f"[bold green]SUCCESS:[/bold green] Found [bold]{len(episodes)}[/bold] episodes to download\n"
        )

        if len(episodes) == 0:
            console.print("[green]No episodes to download![/green]\n")
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

            console.print(table)
            console.print()
            return

        # Initialize S3 client
        s3_client = bucket.get_bucket_client()

        # Download and upload episodes
        successful = 0
        failed = 0

        with Progress(console=console) as progress:
            overall_task = progress.add_task("Processing episodes", total=len(episodes))

            for episode in episodes:
                success = download_episode_mp3(
                    episode, s3_client, console, progress, overall_task
                )

                if success:
                    # Update database with bucket path
                    episode.bucket_mp3_path = generate_bucket_path(episode)
                    db.commit()
                    successful += 1
                else:
                    failed += 1

                progress.update(overall_task, advance=1)

        console.print(
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

            console.print(table)
            console.print()

    finally:
        db.close()


if __name__ == "__main__":
    main()
