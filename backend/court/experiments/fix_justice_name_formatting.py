import difflib

import rl.utils.click as click
import sqlalchemy as sa
from bs4 import BeautifulSoup, NavigableString
from rich.console import Console

from court.db.models import FantasyCourtOpinion
from court.db.session import get_session


def wrap_justice_names_in_html(html: str) -> tuple[str, bool]:
    """
    Wrap justice names in small-caps spans if not already wrapped.

    Returns:
        (modified_html, was_modified)
    """
    soup = BeautifulSoup(html, "html.parser")

    # Patterns to match
    patterns = [
        "Chief Justice Heifetz",
        "Justice Horlbeck",
        "Justice Kelly",
    ]

    def is_in_small_caps(element):
        """Check if element is inside a small-caps span."""
        parent = element.parent
        while parent:
            if (
                parent.name == "span"
                and parent.get("class")
                and "small-caps" in parent.get("class")
            ):
                return True
            parent = parent.parent
        return False

    was_modified = False

    # Process all text nodes
    for text_node in list(soup.find_all(string=True)):
        if not isinstance(text_node, NavigableString):
            continue
        if is_in_small_caps(text_node):
            continue

        text = str(text_node)
        needs_replacement = any(pattern in text for pattern in patterns)

        if not needs_replacement:
            continue

        was_modified = True

        # Build a list of fragments
        fragments = []
        remaining = text

        while remaining:
            # Find the earliest occurrence of any pattern
            earliest_pos = len(remaining)
            earliest_pattern = None

            for pattern in patterns:
                pos = remaining.find(pattern)
                if pos != -1 and pos < earliest_pos:
                    earliest_pos = pos
                    earliest_pattern = pattern

            if earliest_pattern is None:
                # No more patterns found
                if remaining:
                    fragments.append(remaining)
                break

            # Add text before the pattern
            if earliest_pos > 0:
                fragments.append(remaining[:earliest_pos])

            # Add the wrapped pattern
            span = soup.new_tag("span")
            span["class"] = "small-caps"
            span.string = earliest_pattern
            fragments.append(span)

            # Continue with the rest
            remaining = remaining[earliest_pos + len(earliest_pattern) :]

        # Replace the text node with the fragments
        for fragment in reversed(fragments):
            text_node.insert_after(fragment)
        text_node.extract()

    return str(soup), was_modified


@click.command()
@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Print what would be changed without actually updating the database",
)
def main(dry_run: bool):
    """Fix justice name formatting in opinion bodies by wrapping in small-caps spans."""
    console = Console()
    db = get_session()

    # Get all opinions
    opinions = db.execute(sa.select(FantasyCourtOpinion)).scalars().all()

    console.print(f"\n[bold]Found {len(opinions)} opinions to check[/bold]\n")

    modified_count = 0
    modified_opinions = []

    for opinion in opinions:
        modified_html, was_modified = wrap_justice_names_in_html(
            opinion.opinion_body_html
        )

        if was_modified:
            modified_count += 1
            modified_opinions.append((opinion.id, opinion.case_id))
            console.print(
                f"[yellow]Opinion {opinion.id}[/yellow] (Case ID {opinion.case_id}): needs fixing"
            )

            if dry_run:
                # Generate and print diff
                original_lines = opinion.opinion_body_html.splitlines(keepends=True)
                modified_lines = modified_html.splitlines(keepends=True)

                diff = difflib.unified_diff(
                    original_lines,
                    modified_lines,
                    fromfile=f"opinion_{opinion.id}_original",
                    tofile=f"opinion_{opinion.id}_modified",
                    lineterm="",
                )

                console.print("\n[dim]" + "\n".join(diff) + "[/dim]\n")
            else:
                opinion.opinion_body_html = modified_html
                db.commit()
                console.print("  [green]Updated[/green]")

    console.print(f"\n[bold]{modified_count}[/bold] opinions needed fixing")

    if modified_count > 0:
        console.print("\nModified opinions:")
        for opinion_id, case_id in modified_opinions:
            console.print(f"  - Opinion {opinion_id} (Case {case_id})")

    if dry_run and modified_count > 0:
        console.print("\n[yellow]Run without --dry-run to apply changes[/yellow]")
    elif modified_count > 0:
        console.print("\n[green]All changes committed[/green]")
    else:
        console.print("\n[green]No changes needed[/green]")


if __name__ == "__main__":
    main()
