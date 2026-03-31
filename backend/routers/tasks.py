"""
Community Tasks Router - CRUD for DAO tasks.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from backend import models, schemas
from backend.database import get_db

router = APIRouter()


def get_db_dep():
    yield from get_db()


@router.get("/", response_model=schemas.PaginatedResponse[schemas.CommunityTask])
def get_tasks(
    status: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db_dep),
):
    """Get all tasks with optional status filter and pagination."""
    query = db.query(models.CommunityTask)
    if status:
        query = query.filter(models.CommunityTask.status == status)
    
    offset = (page - 1) * size
    total = query.count()
    items = query.offset(offset).limit(size).all()
    pages = (total + size - 1) // size

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


@router.get("/{task_id}", response_model=schemas.CommunityTask)
def get_task(task_id: str, db: Session = Depends(get_db_dep)):
    """Get a specific task."""
    task = (
        db.query(models.CommunityTask)
        .filter(models.CommunityTask.id == task_id)
        .first()
    )
    if not task:
        from backend.errors import ResourceNotFoundError
        raise ResourceNotFoundError(resource="Task", identifier=task_id)
    return task


@router.post("/", response_model=schemas.CommunityTask, status_code=201)
def create_task(task: schemas.CommunityTaskCreate, db: Session = Depends(get_db_dep)):
    """Create a new community task."""
    from uuid import uuid4

    db_task = models.CommunityTask(id=str(uuid4()), **task.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


@router.put("/{task_id}/assign")
def assign_task(task_id: str, user_id: str, db: Session = Depends(get_db_dep)):
    """Assign a task to a user."""
    task = (
        db.query(models.CommunityTask)
        .filter(models.CommunityTask.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.assignee_id = user_id
    task.status = "in_progress"
    db.commit()
    return {"status": "assigned", "task_id": task_id, "assignee_id": user_id}


@router.put("/{task_id}/complete")
def complete_task(task_id: str, db: Session = Depends(get_db_dep)):
    """Mark a task as completed."""
    task = (
        db.query(models.CommunityTask)
        .filter(models.CommunityTask.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "completed"
    db.commit()
    return {"status": "completed", "task_id": task_id, "reward": task.reward}
