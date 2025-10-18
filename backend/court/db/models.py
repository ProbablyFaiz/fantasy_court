from __future__ import annotations

import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


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

    transcripts: Mapped[list[EpisodeTranscript]] = relationship(
        back_populates="episode"
    )
    fantasy_court_segment: Mapped[FantasyCourtSegment | None] = relationship(
        back_populates="episode", uselist=False
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
    provenance: Mapped[Provenance] = relationship()


class EpisodeTranscript(Base, IndexedTimestampMixin):
    __tablename__ = "episode_transcripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("podcast_episodes.id"))

    transcript_json: Mapped[dict] = mapped_column(JSONB)
    provenance_id: Mapped[int] = mapped_column(ForeignKey("provenances.id"))

    episode: Mapped[PodcastEpisode] = relationship(back_populates="transcripts")
    provenance: Mapped[Provenance] = relationship()

    def transcript_obj(self) -> None:
        # TODO: Define a pydantic model for the transcript structure and model_validate the transcript_json here
        pass


class Provenance(Base, IndexedTimestampMixin):
    __tablename__ = "provenances"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_name: Mapped[str] = mapped_column(index=True)
    creator_name: Mapped[str] = mapped_column(index=True)
    record_type: Mapped[str] = mapped_column(index=True)
