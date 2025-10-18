from __future__ import annotations

import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.ext.hybrid import hybrid_property
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

    @hybrid_property
    def has_fantasy_court(self) -> bool:
        return "fantasy court" in self.description.lower()

    @has_fantasy_court.expression
    def has_fantasy_court(cls):
        return func.lower(cls.description).contains("fantasy court")


class EpisodeTranscript(Base, IndexedTimestampMixin):
    __tablename__ = "episode_transcripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("podcast_episodes.id"))

    transcript_json: Mapped[dict] = mapped_column(JSONB)

    episode: Mapped[PodcastEpisode] = relationship(back_populates="transcripts")

    def transcript_obj(self) -> None:
        # TODO: Define a pydantic model for the transcript structure and model_validate the transcript_json here
        pass


class Provenance(Base, IndexedTimestampMixin):
    __tablename__ = "provenances"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_name: Mapped[str] = mapped_column(index=True)
    creator_name: Mapped[str] = mapped_column(index=True)
    record_type: Mapped[str] = mapped_column(index=True)
