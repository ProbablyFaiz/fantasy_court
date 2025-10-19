"""
This file contains the FastAPI app and its routes. Note: As the project grows, you'll
want to use FastAPI's router feature to split the routes into separate files. This is easy;
so it's perfectly alright to keep all routes in this file until it becomes unwieldy.
"""

from pathlib import Path
from typing import Annotated

import sqlalchemy as sa
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload

from court.api.deps import get_case, get_db, get_episode, get_opinion
from court.api.interfaces import (
    CaseItem,
    CaseRead,
    EpisodeItem,
    EpisodeRead,
    OpinionItem,
    OpinionRead,
    PaginatedBase,
)
from court.db.models import FantasyCourtCase, FantasyCourtOpinion, PodcastEpisode
from court.jobs.celery import celery_app
from court.utils.observe import safe_init_sentry

safe_init_sentry()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/health")
def health():
    celery_app.send_task("court.jobs.tasks.healthy_job")
    return {"status": "ok"}


@app.get("/error")
def error():
    celery_app.send_task("court.jobs.tasks.error_job")
    raise Exception("Test error")


# Episode endpoints
@app.get(
    "/episodes",
    response_model=PaginatedBase[EpisodeItem],
    operation_id="listEpisodes",
)
def list_episodes(
    db: Annotated[Session, Depends(get_db)],
    search: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    query = sa.select(PodcastEpisode)

    if search is not None:
        search_filter = f"%{search}%"
        query = query.where(
            sa.or_(
                PodcastEpisode.title.ilike(search_filter),
                PodcastEpisode.description.ilike(search_filter),
            )
        )

    # Get total count
    count_query = sa.select(sa.func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Apply pagination and ordering
    query = (
        query.order_by(PodcastEpisode.pub_date.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    episodes = db.execute(query).scalars().all()

    return PaginatedBase(
        items=episodes,
        total=total,
        page=page,
        size=limit,
    )


@app.get(
    "/episodes/{episode_id}",
    response_model=EpisodeRead,
    operation_id="readEpisode",
)
def read_episode(
    episode: Annotated[PodcastEpisode, Depends(get_episode)],
):
    return episode


# Case endpoints
@app.get(
    "/cases",
    response_model=PaginatedBase[CaseItem],
    operation_id="listCases",
)
def list_cases(
    db: Annotated[Session, Depends(get_db)],
    episode_id: Annotated[int | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    query = sa.select(FantasyCourtCase)

    if episode_id is not None:
        query = query.where(FantasyCourtCase.episode_id == episode_id)

    if search is not None:
        search_filter = f"%{search}%"
        query = query.where(
            sa.or_(
                FantasyCourtCase.case_caption.ilike(search_filter),
                FantasyCourtCase.fact_summary.ilike(search_filter),
                FantasyCourtCase.docket_number.ilike(search_filter),
            )
        )

    # Get total count
    count_query = sa.select(sa.func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Apply pagination and ordering
    query = query.join(PodcastEpisode).order_by(PodcastEpisode.pub_date.desc())
    query = query.offset((page - 1) * limit).limit(limit)
    cases = db.execute(query).scalars().all()

    return PaginatedBase(
        items=cases,
        total=total,
        page=page,
        size=limit,
    )


@app.get(
    "/cases/{case_id}",
    response_model=CaseRead,
    operation_id="readCase",
)
def read_case(
    case: Annotated[FantasyCourtCase, Depends(get_case)],
):
    return case


# Opinion endpoints
@app.get(
    "/opinions",
    response_model=PaginatedBase[OpinionItem],
    operation_id="listOpinions",
)
def list_opinions(
    db: Annotated[Session, Depends(get_db)],
    search: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    query = (
        sa.select(FantasyCourtOpinion)
        .join(FantasyCourtCase)
        .options(selectinload(FantasyCourtOpinion.case))
    )

    if search is not None:
        search_filter = f"%{search}%"
        query = query.where(
            sa.or_(
                FantasyCourtOpinion.holding_statement_html.ilike(search_filter),
                FantasyCourtOpinion.reasoning_summary_html.ilike(search_filter),
                FantasyCourtCase.case_caption.ilike(search_filter),
                FantasyCourtCase.docket_number.ilike(search_filter),
            )
        )

    # Get total count
    count_query = sa.select(sa.func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Apply pagination and ordering
    query = (
        query.join(PodcastEpisode)
        .order_by(PodcastEpisode.pub_date.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    opinions = db.execute(query).scalars().all()

    return PaginatedBase(
        items=opinions,
        total=total,
        page=page,
        size=limit,
    )


@app.get(
    "/opinions/{opinion_id}",
    response_model=OpinionRead,
    operation_id="readOpinion",
)
def read_opinion(
    opinion: Annotated[FantasyCourtOpinion, Depends(get_opinion)],
):
    return opinion


@app.get(
    "/opinions/{opinion_id}/html",
    response_class=HTMLResponse,
    operation_id="readOpinionHtml",
)
def read_opinion_html(
    opinion: Annotated[FantasyCourtOpinion, Depends(get_opinion)],
):
    """Render the opinion as formatted HTML."""
    case = opinion.case
    episode = case.episode

    return templates.TemplateResponse(
        "opinion.html",
        {
            "request": {},  # Required by Jinja2Templates but not used in template
            "case_caption": case.case_caption or "(No Caption)",
            "docket_number": case.docket_number,
            "episode_title": episode.title,
            "episode_date": episode.pub_date.strftime("%B %d, %Y"),
            "authorship_html": opinion.authorship_html,
            "holding_statement_html": opinion.holding_statement_html,
            "reasoning_summary_html": opinion.reasoning_summary_html,
            "opinion_body_html": opinion.opinion_body_html,
        },
    )
