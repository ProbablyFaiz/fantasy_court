"""
This file contains the FastAPI app and its routes. Note: As the project grows, you'll
want to use FastAPI's router feature to split the routes into separate files. This is easy;
so it's perfectly alright to keep all routes in this file until it becomes unwieldy.
"""

from typing import Annotated

import sqlalchemy as sa
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from blank.api.deps import get_db, get_task
from blank.api.interfaces import (
    PaginatedBase,
    TaskCreate,
    TaskListItem,
    TaskRead,
    TaskUpdate,
)
from blank.db.models import Task, TaskPriority
from blank.jobs.celery import celery_app
from blank.utils.observe import safe_init_sentry

safe_init_sentry()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    celery_app.send_task("blank.jobs.tasks.healthy_job")
    return {"status": "ok"}


@app.get("/error")
def error():
    celery_app.send_task("blank.jobs.tasks.error_job")
    raise Exception("Test error")


@app.get(
    "/tasks",
    response_model=PaginatedBase[TaskListItem],
    operation_id="listTasks",
)
def list_tasks(
    db: Annotated[Session, Depends(get_db)],
    completed: bool | None = None,
    priority: TaskPriority | None = None,
    search: Annotated[str, Query()] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    query = sa.select(Task)

    if completed is not None:
        query = query.where(Task.completed == completed)

    if priority is not None:
        query = query.where(Task.priority == priority)

    if search is not None:
        search_filter = f"%{search}%"
        query = query.where(
            sa.or_(
                Task.title.ilike(search_filter),
                Task.description.ilike(search_filter),
            )
        )

    # Get total count
    count_query = sa.select(sa.func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Apply pagination and ordering
    query = (
        query.order_by(Task.created_at.desc()).offset((page - 1) * limit).limit(limit)
    )
    tasks = db.execute(query).unique().scalars().all()

    return PaginatedBase(
        items=tasks,
        total=total,
        page=page,
        size=limit,
    )


@app.post(
    "/tasks",
    response_model=TaskRead,
    operation_id="createTask",
)
def create_task(task: TaskCreate, db: Annotated[Session, Depends(get_db)]):
    db_task = Task(**task.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    return db_task


@app.get(
    "/tasks/{task_id}",
    response_model=TaskRead,
    operation_id="readTask",
)
def read_task(
    task: Annotated[Task, Depends(get_task)],
):
    return task


@app.patch(
    "/tasks/{task_id}",
    response_model=TaskRead,
    operation_id="updateTask",
)
def update_task(
    task_update: TaskUpdate,
    task: Annotated[Task, Depends(get_task)],
    db: Annotated[Session, Depends(get_db)],
):
    update_fields = task_update.model_dump(exclude_unset=True)

    for field, value in update_fields.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)

    return task


@app.delete(
    "/tasks/{task_id}",
    status_code=204,
    operation_id="deleteTask",
)
def delete_task(
    task: Annotated[Task, Depends(get_task)],
    db: Annotated[Session, Depends(get_db)],
):
    db.delete(task)
    db.commit()
