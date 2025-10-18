from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from blank.db.models import Task
from blank.db.session import get_api_session


def get_db() -> Generator[Session, None, None]:
    with get_api_session() as session:
        yield session


def get_task(db: Annotated[Session, Depends(get_db)], task_id: int) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
