import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import events
from .db import get_db
from .deps import current_user, request_id
from .models import Task
from .project_client import get_membership
from .schemas import Status, TaskCreate, TaskOut, TaskUpdate

logger = logging.getLogger("task-service")
router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_and_membership(db: Session, task_id: int, user_id: int, rid: str | None):
    """Задача и роль пользователя в её проекте. Чужая задача выглядит как несуществующая."""
    task = db.get(Task, task_id)
    membership = get_membership(task.project_id, user_id, rid) if task else None
    if not task or not membership:
        raise HTTPException(404, "Task not found")
    return task, membership


def _event_data(task: Task, actor_id: int) -> dict:
    return {
        "task_id": task.id,
        "project_id": task.project_id,
        "title": task.title,
        "status": task.status,
        "assignee_id": task.assignee_id,
        "creator_id": task.creator_id,
        "actor_id": actor_id,
    }


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    data: TaskCreate,
    user: dict = Depends(current_user),
    rid: str | None = Depends(request_id),
    db: Session = Depends(get_db),
):
    if not get_membership(data.project_id, user["id"], rid):
        raise HTTPException(404, "Project not found")
    if data.assignee_id and not get_membership(data.project_id, data.assignee_id, rid):
        raise HTTPException(400, "Assignee is not a project member")

    task = Task(**data.model_dump(), creator_id=user["id"])
    db.add(task)
    db.commit()
    db.refresh(task)
    logger.info("Task created: id=%s project=%s request_id=%s", task.id, task.project_id, rid)

    events.publish("task.created", _event_data(task, user["id"]), rid)
    if task.assignee_id:
        events.publish("task.assigned", _event_data(task, user["id"]), rid)
    return task


@router.get("", response_model=list[TaskOut])
def list_tasks(
    project_id: int = Query(gt=0),
    status: Status | None = None,
    user: dict = Depends(current_user),
    rid: str | None = Depends(request_id),
    db: Session = Depends(get_db),
):
    if not get_membership(project_id, user["id"], rid):
        raise HTTPException(404, "Project not found")
    stmt = select(Task).where(Task.project_id == project_id).order_by(Task.id)
    if status:
        stmt = stmt.where(Task.status == status)
    return db.scalars(stmt).all()


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: int,
    user: dict = Depends(current_user),
    rid: str | None = Depends(request_id),
    db: Session = Depends(get_db),
):
    task, _ = _task_and_membership(db, task_id, user["id"], rid)
    return task


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    data: TaskUpdate,
    user: dict = Depends(current_user),
    rid: str | None = Depends(request_id),
    db: Session = Depends(get_db),
):
    task, _ = _task_and_membership(db, task_id, user["id"], rid)

    changes = data.model_dump(exclude_unset=True)
    # title и status не бывают пустыми, а assignee_id=null означает "снять исполнителя"
    for field in ("title", "status"):
        if field in changes and changes[field] is None:
            changes.pop(field)

    new_assignee = changes.get("assignee_id")
    if new_assignee and not get_membership(task.project_id, new_assignee, rid):
        raise HTTPException(400, "Assignee is not a project member")

    old_status, old_assignee = task.status, task.assignee_id
    for field, value in changes.items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    logger.info("Task updated: id=%s request_id=%s", task.id, rid)

    if task.status != old_status:
        events.publish(
            "task.status_changed",
            {**_event_data(task, user["id"]), "old_status": old_status, "new_status": task.status},
            rid,
        )
    if task.assignee_id and task.assignee_id != old_assignee:
        events.publish("task.assigned", _event_data(task, user["id"]), rid)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    user: dict = Depends(current_user),
    rid: str | None = Depends(request_id),
    db: Session = Depends(get_db),
):
    task, membership = _task_and_membership(db, task_id, user["id"], rid)
    if task.creator_id != user["id"] and membership["role"] != "owner":
        raise HTTPException(403, "Only the task author or project owner can delete it")
    db.delete(task)
    db.commit()
    logger.info("Task deleted: id=%s request_id=%s", task_id, rid)