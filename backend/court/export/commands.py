"""CLI commands for Fantasy Court data export operations."""

from pathlib import Path

import rl.utils.click as click

from court.export import export_pdfs
from court.export.export_opinions import _DEFAULT_OUTPUT_DIR, export_opinions


@click.group()
def export():
    """Fantasy Court data export utilities."""
    pass


@export.command()
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=_DEFAULT_OUTPUT_DIR,
    help="Directory to export opinions to",
)
def opinions(output_dir: Path):
    """Export all opinions to static JSON files for frontend consumption.

    This command exports all Fantasy Court opinions to JSON format suitable
    for static site generation. Creates an index.json with opinion metadata
    and individual JSON files for each full opinion.
    """
    export_opinions(output_dir)


@export.command()
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=export_pdfs._DEFAULT_OUTPUT_DIR,
    help="Directory to write {docket_number}.pdf files to",
)
@click.option(
    "--font-dir",
    "-f",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=export_pdfs._DEFAULT_FONT_DIR,
    help="Directory containing the Equity A and OPTIEngraversOldEnglish .otf files",
)
def pdfs(output_dir: Path, font_dir: Path):
    """Typeset every opinion as a slip-opinion PDF booklet with Typst."""
    export_pdfs.export_pdfs(output_dir, font_dir)
