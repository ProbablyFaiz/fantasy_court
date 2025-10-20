from __future__ import annotations

import math
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, computed_field


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


DataT = TypeVar("DataT")


class PaginatedBase(ApiModel, Generic[DataT]):
    items: list[DataT]
    total: int
    page: int
    size: int

    @computed_field
    def next_page(self) -> int | None:
        return self.page + 1 if self.page * self.size < self.total else None

    @computed_field
    def num_pages(self) -> int:
        return math.ceil(self.total / self.size) if self.size > 0 else 0


# Episode interfaces
class EpisodeBase(ApiModel):
    id: int
    guid: str
    title: str
    description_html: str | None
    pub_date: datetime
    duration_seconds: int | None
    bucket_mp3_public_url: str | None


class EpisodeItem(EpisodeBase):
    """Episode in list views."""

    pass


class EpisodeRead(EpisodeBase):
    """Full episode with related cases."""

    fantasy_court_cases: list[CaseItem]


# Case interfaces
class CaseBase(ApiModel):
    id: int
    docket_number: str
    case_caption: str | None
    fact_summary: str
    questions_presented_html: str | None
    procedural_posture: str | None
    case_topics: list[str] | None
    start_time_s: float
    end_time_s: float


class CaseItem(CaseBase):
    """Case in list views or as related object."""

    episode: EpisodeItem


# Opinion interfaces - defined early to avoid circular imports
class CitedOpinionItem(ApiModel):
    """Minimal opinion information for citations - avoids circular dependency."""

    id: int
    authorship_html: str
    holding_statement_html: str


class CitedCaseItem(ApiModel):
    """Minimal case information for citations."""

    id: int
    docket_number: str
    case_caption: str | None
    episode_id: int
    opinion: CitedOpinionItem | None


class CaseRead(CaseBase):
    """Full case with episode and opinion."""

    episode: EpisodeItem
    opinion: OpinionItem | None
    cases_cited: list[CitedCaseItem]
    cases_citing: list[CitedCaseItem]


# Full Opinion interfaces
class OpinionBase(ApiModel):
    id: int
    authorship_html: str
    holding_statement_html: str
    reasoning_summary_html: str
    pdf_path: str | None


class OpinionItem(OpinionBase):
    """Opinion in list views."""

    case: CaseItem


class OpinionRead(OpinionBase):
    """Full opinion with complete body and case context."""

    opinion_body_html: str
    case: CaseRead
