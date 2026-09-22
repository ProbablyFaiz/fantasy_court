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


def remove_stale(directory: Path, suffix: str, dockets: set[str]) -> None:
    """Delete exported files for opinions that no longer exist, so the static
    build never renders a leftover from an older export."""
    for path in directory.glob(f"*.{suffix}"):
        if path.stem not in dockets:
            path.unlink()


def select_opinions() -> sa.Select[tuple[FantasyCourtOpinion]]:
    """All opinions, newest first, with everything OpinionRead serializes loaded."""
    return (
        sa.select(FantasyCourtOpinion)
        .join(FantasyCourtOpinion.case)
        .outerjoin(FantasyCourtCase.episode)
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
        .order_by(
            sa.func.coalesce(
                PodcastEpisode.pub_date, FantasyCourtCase.created_at
            ).desc()
        )
    )


def export_opinions(output_dir: Path) -> None:
    """Export all opinions to JSON files for static site generation.

    Creates:
        - index.json: List of OpinionItem objects with metadata, listed opinions only
        - opinions/{docket_number}.json: Full OpinionRead for each opinion, listed or not

    Unlisted opinions are reachable by URL but never appear in the index or in a
    listed opinion's "cited by" list.
    """
    session: Session = get_session()

    # Create output directories
    output_dir.mkdir(parents=True, exist_ok=True)
    opinions_dir = output_dir / "opinions"
    opinions_dir.mkdir(exist_ok=True)

    opinions = session.execute(select_opinions()).scalars().all()
    unlisted_case_ids = {
        opinion.case.id for opinion in opinions if opinion.case.unlisted
    }

    # Export index.json with OpinionItem models
    opinion_items = [
        OpinionItem.model_validate(opinion)
        for opinion in opinions
        if not opinion.case.unlisted
    ]
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
        if not opinion.case.unlisted:
            opinion_read.case.cases_citing = [
                citing
                for citing in opinion_read.case.cases_citing
                if citing.id not in unlisted_case_ids
            ]

        opinion_path = opinions_dir / f"{opinion_read.case.docket_number}.json"
        with opinion_path.open("w") as f:
            json.dump(opinion_read.model_dump(mode="json"), f, indent=2)

        pbar.set_postfix({"docket": opinion_read.case.docket_number})

    remove_stale(opinions_dir, "json", {o.case.docket_number for o in opinions})
    print(f"Exported {len(opinions)} opinions to {output_dir}")
    print(f"  - index.json: {len(opinion_items)} opinion items")
    print(
        f"  - opinions/: {len(opinions)} full opinions ({len(unlisted_case_ids)} unlisted)"
    )
