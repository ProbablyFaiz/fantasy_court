from collections.abc import Generator
from typing import Annotated

import sqlalchemy as sa
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from court.db.models import (
    FantasyCourtCase,
    FantasyCourtOpinion,
    PodcastEpisode,
)
from court.db.session import get_api_session


def get_db() -> Generator[Session, None, None]:
    with get_api_session() as session:
        yield session


def get_episode(
    db: Annotated[Session, Depends(get_db)], episode_id: int
) -> PodcastEpisode:
    query = (
        sa.select(PodcastEpisode)
        .where(PodcastEpisode.id == episode_id)
        .options(selectinload(PodcastEpisode.fantasy_court_cases))
    )
    episode = db.execute(query).scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


def get_case(db: Annotated[Session, Depends(get_db)], case_id: int) -> FantasyCourtCase:
    query = (
        sa.select(FantasyCourtCase)
        .where(FantasyCourtCase.id == case_id)
        .options(
            selectinload(FantasyCourtCase.episode),
            selectinload(FantasyCourtCase.opinion),
            selectinload(FantasyCourtCase.cases_cited),
            selectinload(FantasyCourtCase.cases_citing),
        )
    )
    case = db.execute(query).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def get_opinion(
    db: Annotated[Session, Depends(get_db)], opinion_id: int
) -> FantasyCourtOpinion:
    query = (
        sa.select(FantasyCourtOpinion)
        .where(FantasyCourtOpinion.id == opinion_id)
        .options(
            selectinload(FantasyCourtOpinion.case).selectinload(
                FantasyCourtCase.episode
            )
        )
    )
    opinion = db.execute(query).scalar_one_or_none()
    if not opinion:
        raise HTTPException(status_code=404, detail="Opinion not found")
    return opinion
