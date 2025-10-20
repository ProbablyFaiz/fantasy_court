"""CLI commands for Fantasy Court automated pipeline operations."""

import os
import subprocess
from pathlib import Path

import rl.utils.click as click
import rl.utils.io

from court.utils.print import CONSOLE


@click.group()
def pipeline():
    """Fantasy Court automated pipeline utilities."""
    rl.utils.io.ensure_dotenv_loaded()


@pipeline.command()
def run():
    """
    Run the complete Fantasy Court automated pipeline.

    This command runs all steps to process Fantasy Court content end-to-end:
    1. Ingests new episodes from RSS feed
    2. Downloads episode MP3s to S3
    3. Creates segments for new episodes
    4. Transcribes segments
    5. Extracts cases from segments
    6. Drafts opinions for cases
    7. Creates citations between opinions
    8. Exports opinions to JSON
    9. Builds Next.js static site
    10. Deploys to Cloudflare Pages
    """
    # Get frontend-static path from env (required)
    frontend_path = os.getenv("FANTASY_COURT_FRONTEND_STATIC_PATH")
    if not frontend_path:
        raise ValueError(
            "FANTASY_COURT_FRONTEND_STATIC_PATH environment variable must be set. "
            "Please set it to the path of your frontend-static directory."
        )

    frontend_path = Path(frontend_path).resolve()

    # Get Cloudflare Pages project name from env (required)
    cf_project_name = os.getenv("CLOUDFLARE_PAGES_PROJECT_NAME")
    if not cf_project_name:
        raise ValueError(
            "CLOUDFLARE_PAGES_PROJECT_NAME environment variable must be set. "
            "Please set it to your Cloudflare Pages project name."
        )

    CONSOLE.print("[bold blue]Starting Fantasy Court Pipeline[/bold blue]")
    CONSOLE.print(f"[dim]Frontend path: {frontend_path}[/dim]")
    CONSOLE.print(f"[dim]Cloudflare Pages project: {cf_project_name}[/dim]\n")

    steps = [
        ("Ingesting episodes from RSS", ["court", "ingest", "fetch-episodes"]),
        ("Downloading episode MP3s", ["court", "ingest", "download-episodes"]),
        ("Creating segments", ["court", "inference", "create-segments"]),
        ("Transcribing segments", ["court", "inference", "transcribe-segments"]),
        ("Extracting cases", ["court", "inference", "create-cases"]),
        (
            "Drafting opinions",
            ["court", "inference", "create-opinions", "--concurrency", "1"],
        ),
        ("Creating citations", ["court", "inference", "create-citations"]),
        (
            "Exporting opinions",
            [
                "court",
                "export",
                "opinions",
                "--output-dir",
                str(frontend_path / "public" / "data"),
            ],
        ),
    ]

    # Run each backend step
    for step_name, command in steps:
        CONSOLE.print(f"[cyan]Step:[/cyan] {step_name}")
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            CONSOLE.print(f"[green]✓[/green] {step_name} completed")
            if result.stdout:
                CONSOLE.print(f"[dim]{result.stdout}[/dim]")
        except subprocess.CalledProcessError as e:
            CONSOLE.print(f"[red]✗[/red] {step_name} failed: {e}")
            CONSOLE.print(f"[red]Error output:[/red]\n{e.stderr}")
            # Continue despite errors to ensure other steps run
            continue

    # Build Next.js site
    CONSOLE.print("[cyan]Step:[/cyan] Building Next.js static site")
    try:
        subprocess.run(
            ["pnpm", "run", "build"],
            cwd=str(frontend_path),
            check=True,
            capture_output=True,
            text=True,
        )
        CONSOLE.print("[green]✓[/green] Next.js build completed")
    except subprocess.CalledProcessError as e:
        CONSOLE.print(f"[red]✗[/red] Next.js build failed: {e}")
        CONSOLE.print(f"[red]Error output:[/red]\n{e.stderr}")
        return

    # Deploy to Cloudflare Pages
    CONSOLE.print("[cyan]Step:[/cyan] Deploying to Cloudflare Pages")
    try:
        result = subprocess.run(
            ["wrangler", "pages", "deploy", "out", "--project-name", cf_project_name],
            cwd=str(frontend_path),
            check=True,
            capture_output=True,
            text=True,
        )
        CONSOLE.print("[green]✓[/green] Cloudflare Pages deployment completed")
        CONSOLE.print(f"[dim]{result.stdout}[/dim]")
    except subprocess.CalledProcessError as e:
        CONSOLE.print(f"[red]✗[/red] Cloudflare Pages deployment failed: {e}")
        CONSOLE.print(f"[red]Error output:[/red]\n{e.stderr}")
        return

    CONSOLE.print(
        "\n[bold green]Fantasy Court Pipeline completed successfully![/bold green]"
    )
