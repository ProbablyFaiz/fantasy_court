from __future__ import annotations

import datetime

from sqlalchemy import ARRAY, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from court.inference.transcript import Transcript


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
    )


class IndexedTimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        index=True,
    )


class PodcastEpisode(Base, IndexedTimestampMixin):
    __tablename__ = "podcast_episodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    guid: Mapped[str] = mapped_column(index=True, unique=True)
    title: Mapped[str] = mapped_column(index=True)
    description: Mapped[str | None] = mapped_column()
    description_html: Mapped[str | None] = mapped_column()
    pub_date: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), index=True
    )

    duration_seconds: Mapped[int | None] = mapped_column()
    rss_feed_url: Mapped[str | None] = mapped_column()
    canonical_mp3_url: Mapped[str | None] = mapped_column()
    bucket_mp3_path: Mapped[str | None] = mapped_column()

    transcript: Mapped[EpisodeTranscript | None] = relationship(
        back_populates="episode", uselist=False
    )
    fantasy_court_segment: Mapped[FantasyCourtSegment | None] = relationship(
        back_populates="episode", uselist=False
    )
    fantasy_court_cases: Mapped[list[FantasyCourtCase]] = relationship(
        back_populates="episode"
    )


class FantasyCourtSegment(Base, IndexedTimestampMixin):
    __tablename__ = "fantasy_court_segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("podcast_episodes.id"))
    start_time_s: Mapped[float | None] = mapped_column()
    end_time_s: Mapped[float | None] = mapped_column()

    provenance_id: Mapped[int] = mapped_column(ForeignKey("provenances.id"))

    episode: Mapped[PodcastEpisode] = relationship(
        back_populates="fantasy_court_segment"
    )
    transcript: Mapped[EpisodeTranscript | None] = relationship(
        back_populates="segment", uselist=False
    )
    fantasy_court_cases: Mapped[list[FantasyCourtCase]] = relationship(
        back_populates="segment"
    )
    provenance: Mapped[Provenance] = relationship()


class EpisodeTranscript(Base, IndexedTimestampMixin):
    __tablename__ = "episode_transcripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("podcast_episodes.id"))
    segment_id: Mapped[int | None] = mapped_column(
        ForeignKey("fantasy_court_segments.id")
    )

    transcript_json: Mapped[dict] = mapped_column(JSONB)
    start_time_s: Mapped[float] = mapped_column()
    end_time_s: Mapped[float] = mapped_column()

    provenance_id: Mapped[int] = mapped_column(ForeignKey("provenances.id"))

    episode: Mapped[PodcastEpisode] = relationship(back_populates="transcript")
    provenance: Mapped[Provenance] = relationship()
    segment: Mapped[FantasyCourtSegment | None] = relationship(
        back_populates="transcript"
    )

    def transcript_obj(self) -> Transcript:
        """Parse and validate the transcript JSON into a Pydantic model."""
        return Transcript.model_validate(self.transcript_json)


class FantasyCourtCase(Base, IndexedTimestampMixin):
    __tablename__ = "fantasy_court_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("podcast_episodes.id"))
    segment_id: Mapped[int] = mapped_column(ForeignKey("fantasy_court_segments.id"))
    provenance_id: Mapped[int] = mapped_column(ForeignKey("provenances.id"))

    docket_number: Mapped[str] = mapped_column(index=True, unique=True)
    """The last two digits of the year of the episode's publication,
    followed by the zero-padded 4-digit ID of the episode, followed by a 1-indexed sequential number
    on how many cases into the episode this is. Example: 25-0197-1, 25-0197-2, for episode 197 published in 2025."""
    start_time_s: Mapped[float] = mapped_column()
    end_time_s: Mapped[float] = mapped_column()

    fact_summary: Mapped[str] = mapped_column()
    """A summary of the facts of the case."""
    case_caption: Mapped[str | None] = mapped_column()
    """A short caption for the case, e.g. "Alec v. Nick", "In re. roster management during wife's labor", "People v. Taysom Hill" """
    questions_presented_html: Mapped[str | None] = mapped_column()
    """The legal question(s) before the court."""
    procedural_posture: Mapped[str | None] = mapped_column()
    """How the case arrived at the court, e.g. "Appeal from the Commissioner's ruling" or "Original petition for relief"."""
    case_topics: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    """Categorical tags like "corrupt dealing", "scoring dispute", "retroactive substitution", "waiver wire", "blackmail"."""

    episode: Mapped[PodcastEpisode] = relationship(back_populates="fantasy_court_cases")
    segment: Mapped[FantasyCourtSegment] = relationship(
        back_populates="fantasy_court_cases"
    )
    provenance: Mapped[Provenance] = relationship()
    citing_cases: Mapped[list[CaseCitation]] = relationship(
        foreign_keys="CaseCitation.cited_case_id", back_populates="cited_case"
    )
    cited_cases: Mapped[list[CaseCitation]] = relationship(
        foreign_keys="CaseCitation.citing_case_id", back_populates="citing_case"
    )


class FantasyCourtOpinion(Base, IndexedTimestampMixin):
    __tablename__ = "fantasy_court_opinions"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("fantasy_court_cases.id"))
    provenance_id: Mapped[int] = mapped_column(ForeignKey("provenances.id"))

    authorship_html: Mapped[str] = mapped_column()
    """The HTML markup for the authorship of the opinion. For instance:
    "<span class="small-caps">Justice Horlbeck</span> delivered the opinion of the Court, in which <span class="small-caps">Justice Heifetz</span> joined.
    <span class="small-caps">Justice Kelly</span> filed a dissenting opinion." Or, "<span class="small-caps">Per Curiam</span>. Or "[majority info] <span class="small-caps">Justice Kelly</span> filed an opinion concurring in part and dissenting in part."
    """
    opinion_body_html: Mapped[str] = mapped_column()
    """The HTML markup for the body of the opinion."""
    holding_statement_html: Mapped[str] = mapped_column()
    """The HTML markup for the holding statement of the opinion. E.g. "<em>Held:</em> Trade made by league commissioner with his father-in-law to swap injured Stefon Diggs for healthy Marvin Harrison Jr. is void."""
    reasoning_summary_html: Mapped[str] = mapped_column()
    """The HTML markup summarizing the legal reasoning and framework applied in the opinion."""

    pdf_path: Mapped[str | None] = mapped_column()
    """The path to the PDF file in the bucket. If None, the opinion has not been generated yet."""

    case: Mapped[FantasyCourtCase] = relationship()
    provenance: Mapped[Provenance] = relationship()


class CaseCitation(Base, IndexedTimestampMixin):
    __tablename__ = "case_citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    citing_case_id: Mapped[int] = mapped_column(
        ForeignKey("fantasy_court_cases.id"), index=True
    )
    cited_case_id: Mapped[int] = mapped_column(
        ForeignKey("fantasy_court_cases.id"), index=True
    )
    citation_context: Mapped[str | None] = mapped_column()
    """Optional context about how/why this case was cited."""

    citing_case: Mapped[FantasyCourtCase] = relationship(
        foreign_keys=[citing_case_id], back_populates="cited_cases"
    )
    cited_case: Mapped[FantasyCourtCase] = relationship(
        foreign_keys=[cited_case_id], back_populates="citing_cases"
    )


class Provenance(Base, IndexedTimestampMixin):
    __tablename__ = "provenances"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_name: Mapped[str] = mapped_column(index=True)
    creator_name: Mapped[str] = mapped_column(index=True)
    record_type: Mapped[str] = mapped_column(index=True)
