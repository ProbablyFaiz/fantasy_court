from __future__ import annotations

import datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy import String
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=sa.func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=sa.func.now(), server_onupdate=sa.func.now()
    )


class IndexedTimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=sa.func.now(), index=True
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=sa.func.now(), server_onupdate=sa.func.now(), index=True
    )


class TaskPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Task(Base, IndexedTimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column()
    completed: Mapped[bool] = mapped_column(server_default=sa.text("false"))
    priority: Mapped[TaskPriority] = mapped_column(String())
