"""Export Fantasy Court opinions to static JSON files for frontend consumption."""

import json
import re
from pathlib import Path

import rl.utils.io
import smartypants
import sqlalchemy as sa
import tqdm
from sqlalchemy.orm import Session, selectinload

from court.api.interfaces import OpinionItem, OpinionRead
from court.db.models import FantasyCourtCase, FantasyCourtOpinion, PodcastEpisode
from court.db.session import get_session

_DEFAULT_OUTPUT_DIR = rl.utils.io.get_data_path("export", "opinions")


def _fix_post_tag_apostrophes(text: str) -> str:
    """Fix smartypants incorrectly using left quotes after tags instead of apostrophes.

    When text like <span>don</span>'t appears, smartypants converts ' to left quote
    instead of apostrophe because the tag interrupts the word.
    """
    return re.sub(r"(>)&#8216;([a-zA-Z])", r"\1&#8217;\2", text)


def _smart_quote_html(text: str) -> str:
    """Apply smartypants to the text."""
    return _fix_post_tag_apostrophes(smartypants.smartypants(text))


def apply_smartypants(opinion: OpinionItem | OpinionRead):
    """Apply smartypants to the opinion."""
    opinion.authorship_html = _smart_quote_html(opinion.authorship_html)
    opinion.holding_statement_html = _smart_quote_html(opinion.holding_statement_html)
    opinion.reasoning_summary_html = _smart_quote_html(opinion.reasoning_summary_html)
    opinion.case.case_caption = _smart_quote_html(opinion.case.case_caption)
    opinion.case.fact_summary = _smart_quote_html(opinion.case.fact_summary)
    opinion.case.questions_presented_html = _smart_quote_html(
        opinion.case.questions_presented_html
    )
    opinion.case.procedural_posture = _smart_quote_html(opinion.case.procedural_posture)
    if hasattr(opinion, "opinion_body_html"):
        opinion.opinion_body_html = _smart_quote_html(opinion.opinion_body_html)

    return opinion


def export_opinions(output_dir: Path) -> None:
    """Export all opinions to JSON files for static site generation.

    Creates:
        - index.json: List of OpinionItem objects with metadata
        - opinions/{docket_number}.json: Full OpinionRead for each opinion
    """
    session: Session = get_session()

    # Create output directories
    output_dir.mkdir(parents=True, exist_ok=True)
    opinions_dir = output_dir / "opinions"
    opinions_dir.mkdir(exist_ok=True)

    # Query all opinions with eager loading for related data
    query = (
        sa.select(FantasyCourtOpinion)
        .join(FantasyCourtOpinion.case)
        .join(FantasyCourtCase.episode)
        .options(
            selectinload(FantasyCourtOpinion.case).selectinload(
                FantasyCourtCase.episode
            ),
            selectinload(FantasyCourtOpinion.case)
            .selectinload(FantasyCourtCase.cases_cited)
            .selectinload(FantasyCourtCase.opinion),
            selectinload(FantasyCourtOpinion.case)
            .selectinload(FantasyCourtCase.cases_citing)
            .selectinload(FantasyCourtCase.opinion),
        )
        .order_by(PodcastEpisode.pub_date.desc())
    )

    opinions = session.execute(query).scalars().all()

    # Export index.json with OpinionItem models
    opinion_items = [OpinionItem.model_validate(opinion) for opinion in opinions]
    for opinion_item in opinion_items:
        apply_smartypants(opinion_item)

    index_path = output_dir / "index.json"
    with index_path.open("w") as f:
        json.dump(
            [opinion_item.model_dump(mode="json") for opinion_item in opinion_items],
            f,
            indent=2,
        )

    # Export individual opinion files with OpinionRead models
    pbar = tqdm.tqdm(opinions, desc="Exporting opinions")
    for opinion in pbar:
        opinion_read = OpinionRead.model_validate(opinion)
        apply_smartypants(opinion_read)

        opinion_path = opinions_dir / f"{opinion_read.case.docket_number}.json"
        with opinion_path.open("w") as f:
            json.dump(opinion_read.model_dump(mode="json"), f, indent=2)

        pbar.set_postfix({"docket": opinion_read.case.docket_number})

    print(f"Exported {len(opinions)} opinions to {output_dir}")
    print(f"  - index.json: {len(opinion_items)} opinion items")
    print(f"  - opinions/: {len(opinions)} full opinions")
