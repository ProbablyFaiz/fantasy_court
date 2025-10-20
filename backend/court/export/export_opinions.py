"""Export Fantasy Court opinions to static JSON files for frontend consumption."""

import json
from pathlib import Path
from typing import Any

import rl.utils.io
import smartypants
import sqlalchemy as sa
import tqdm
from sqlalchemy.orm import Session, selectinload

from court.api.interfaces import OpinionItem, OpinionRead
from court.db.models import FantasyCourtCase, FantasyCourtOpinion, PodcastEpisode
from court.db.session import get_session

_DEFAULT_OUTPUT_DIR = rl.utils.io.get_data_path("export", "opinions")


def apply_smartypants(data: Any) -> Any:
    """Recursively apply smartypants to all HTML string fields in data structure."""
    if isinstance(data, dict):
        return {
            key: (
                smartypants.smartypants(value)
                if isinstance(value, str)
                and key
                in (
                    "authorship_html",
                    "holding_statement_html",
                    "reasoning_summary_html",
                    "opinion_body_html",
                    "case_caption",
                )
                else apply_smartypants(value)
            )
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [apply_smartypants(item) for item in data]
    else:
        return data


def export_opinions(output_dir: Path) -> None:
    """Export all opinions to JSON files for static site generation.

    Creates:
        - index.json: List of OpinionItem objects with metadata
        - opinions/{id}.json: Full OpinionRead for each opinion
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
    index_data = [item.model_dump(mode="json") for item in opinion_items]

    # Apply smart quotes to HTML fields
    index_data = apply_smartypants(index_data)

    index_path = output_dir / "index.json"
    with index_path.open("w") as f:
        json.dump(index_data, f, indent=2)

    # Export individual opinion files with OpinionRead models
    pbar = tqdm.tqdm(opinions, desc="Exporting opinions")
    for opinion in pbar:
        opinion_read = OpinionRead.model_validate(opinion)
        opinion_data = opinion_read.model_dump(mode="json")

        # Apply smart quotes to HTML fields
        opinion_data = apply_smartypants(opinion_data)

        opinion_path = opinions_dir / f"{opinion.id}.json"
        with opinion_path.open("w") as f:
            json.dump(opinion_data, f, indent=2)

        pbar.set_postfix({"id": opinion.id})

    print(f"Exported {len(opinions)} opinions to {output_dir}")
    print(f"  - index.json: {len(opinion_items)} opinion items")
    print(f"  - opinions/: {len(opinions)} full opinions")
