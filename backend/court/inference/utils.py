"""Utility functions for inference operations."""

import click
import sqlalchemy as sa
from sqlalchemy.orm import Session

from court.db.models import Provenance


def get_or_create_provenance(
    db: Session,
    task_name: str,
    creator_name: str,
    record_type: str,
) -> Provenance:
    """
    Get or create a provenance record.

    Args:
        db: Database session
        task_name: Name of the task
        creator_name: Name of the creator/model
        record_type: Type of records being created

    Returns:
        Provenance record
    """
    provenance = db.execute(
        sa.select(Provenance).where(
            Provenance.task_name == task_name,
            Provenance.creator_name == creator_name,
            Provenance.record_type == record_type,
        )
    ).scalar_one_or_none()

    if not provenance:
        provenance = Provenance(
            task_name=task_name,
            creator_name=creator_name,
            record_type=record_type,
        )
        db.add(provenance)
        db.flush()
        db.refresh(provenance)

    return provenance


def should_save_prompt(
    save_option: str,
    prompt_message: str = "Save to the database?",
) -> bool:
    """
    Determine if user wants to save based on save option.

    Args:
        save_option: One of 'yes', 'ask', or 'no'
        prompt_message: Message to show when asking user

    Returns:
        True if should save, False otherwise
    """
    if save_option == "yes":
        return True
    elif save_option == "ask":
        return click.confirm(f"\n{prompt_message}", default=False)
    else:
        return False
