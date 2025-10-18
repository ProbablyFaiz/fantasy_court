from __future__ import annotations

import datetime

from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
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
    guid: Mapped[str] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(index=True)
    description: Mapped[str | None] = mapped_column()
    description_html: Mapped[str | None] = mapped_column()
    pub_date: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), index=True
    )

    duration_seconds: Mapped[int | None] = mapped_column()
    canonical_mp3_url: Mapped[str | None] = mapped_column()
    rss_feed_url: Mapped[str | None] = mapped_column()
