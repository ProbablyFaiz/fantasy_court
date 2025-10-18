import math
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, computed_field

from blank.db.models import TaskPriority


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


class TaskCreate(ApiModel):
    title: str
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM


class TaskBase(ApiModel):
    id: int
    title: str
    completed: bool
    priority: TaskPriority
    description: str | None
    created_at: datetime
    updated_at: datetime


class TaskRead(TaskBase):
    pass


class TaskListItem(TaskBase):
    pass


class TaskUpdate(ApiModel):
    title: str | None = None
    description: str | None = None
    completed: bool | None = None
    priority: TaskPriority | None = None
