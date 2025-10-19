import rl.utils.click as click
import sqlalchemy as sa
from bs4 import BeautifulSoup
from rich.console import Console
from sqlalchemy.orm import Session

from court.db.models import CaseCitation, FantasyCourtCase, FantasyCourtOpinion
from court.db.session import get_session


def extract_citations(opinion_html: str) -> list[str]:
    """
    Extract all cited docket numbers from opinion HTML.

    Returns:
        List of unique docket numbers cited in the opinion
    """
    soup = BeautifulSoup(opinion_html, "lxml")
    citation_spans = soup.find_all("span", attrs={"data-cite-docket": True})

    docket_numbers = []
    for span in citation_spans:
        docket = span.get("data-cite-docket")
        if docket:
            docket_numbers.append(docket)

    return list(set(docket_numbers))


def process_opinion_citations(
    db: Session, opinion: FantasyCourtOpinion, console: Console
) -> tuple[int, int]:
    """
    Process citations for a single opinion.

    Returns:
        Tuple of (citations_created, citations_skipped)
    """
    citing_case = opinion.case

    # Extract all cited docket numbers from the opinion body
    cited_docket_numbers = extract_citations(opinion.opinion_body_html)

    if not cited_docket_numbers:
        return 0, 0

    # Build a lookup map of docket number -> case ID
    cited_cases_query = sa.select(FantasyCourtCase).where(
        FantasyCourtCase.docket_number.in_(cited_docket_numbers)
    )
    cited_cases = db.execute(cited_cases_query).scalars().all()
    docket_to_case = {case.docket_number: case for case in cited_cases}

    # Track missing citations
    missing_dockets = set(cited_docket_numbers) - set(docket_to_case.keys())
    if missing_dockets:
        console.print(
            f"  [yellow]Warning:[/yellow] Opinion {opinion.id} cites "
            f"non-existent docket(s): {', '.join(sorted(missing_dockets))}"
        )

    created = 0
    skipped = 0

    for cited_docket in cited_docket_numbers:
        cited_case = docket_to_case.get(cited_docket)
        if not cited_case:
            skipped += 1
            continue

        # Check if citation already exists
        existing = db.execute(
            sa.select(CaseCitation).where(
                CaseCitation.citing_case_id == citing_case.id,
                CaseCitation.cited_case_id == cited_case.id,
            )
        ).scalar_one_or_none()

        if existing:
            skipped += 1
            continue

        # Create new citation
        citation = CaseCitation(
            citing_case_id=citing_case.id,
            cited_case_id=cited_case.id,
        )
        db.add(citation)
        created += 1

    return created, skipped


@click.command()
def main():
    """Extract and populate citations from Fantasy Court opinions."""
    console = Console()

    console.print("\n[bold blue]Extracting citations from opinions...[/bold blue]\n")

    db = get_session()

    # Get all opinions
    opinions_query = sa.select(FantasyCourtOpinion).options(
        sa.orm.selectinload(FantasyCourtOpinion.case)
    )
    opinions = db.execute(opinions_query).scalars().all()

    console.print(f"Found {len(opinions)} opinions to process\n")

    total_created = 0
    total_skipped = 0

    for opinion in opinions:
        created, skipped = process_opinion_citations(db, opinion, console)
        total_created += created
        total_skipped += skipped

        if created > 0:
            console.print(
                f"  [green]✓[/green] Opinion {opinion.id} "
                f"(docket {opinion.case.docket_number}): "
                f"{created} citation(s) created"
            )

    # Commit all citations
    db.commit()

    console.print(
        f"\n[bold green]SUCCESS:[/bold green] Created [bold cyan]{total_created}[/bold cyan] citations"
    )
    if total_skipped > 0:
        console.print(
            f"[dim]Skipped {total_skipped} existing or invalid citations[/dim]"
        )

    console.print()


if __name__ == "__main__":
    main()
