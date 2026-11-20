import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .deps import current_user
from .models import Member, Project
from .schemas import MemberAdd, MemberOut, ProjectCreate, ProjectOut

logger = logging.getLogger("project-service")
router = APIRouter(prefix="/api/projects", tags=["projects"])
internal = APIRouter(prefix="/internal", tags=["internal"])


def _get_project_for(db: Session, project_id: int, user_id: int) -> tuple[Project, Member]:
    """Проект и членство пользователя. Чужой проект выглядит как несуществующий (404)."""
    project = db.get(Project, project_id)
    member = db.get(Member, (project_id, user_id)) if project else None
    if not project or not member:
        raise HTTPException(404, "Project not found")
    return project, member


def _require_owner(member: Member):
    if member.role != "owner":
        raise HTTPException(403, "Only the owner can do this")


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    data: ProjectCreate, user: dict = Depends(current_user), db: Session = Depends(get_db)
):
    project = Project(name=data.name, description=data.description, owner_id=user["id"])
    db.add(project)
    db.flush()  # получаем project.id до commit
    db.add(Member(project_id=project.id, user_id=user["id"], role="owner"))
    db.commit()
    db.refresh(project)
    logger.info("Project created: id=%s owner=%s", project.id, user["id"])
    return project


@router.get("", response_model=list[ProjectOut])
def list_my_projects(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    stmt = (
        select(Project)
        .join(Member, Member.project_id == Project.id)
        .where(Member.user_id == user["id"])
        .order_by(Project.id)
    )
    return db.scalars(stmt).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, user: dict = Depends(current_user), db: Session = Depends(get_db)):
    project, _ = _get_project_for(db, project_id, user["id"])
    return project


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    data: ProjectCreate,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    project, member = _get_project_for(db, project_id, user["id"])
    _require_owner(member)
    project.name = data.name
    project.description = data.description
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, user: dict = Depends(current_user), db: Session = Depends(get_db)):
    project, member = _get_project_for(db, project_id, user["id"])
    _require_owner(member)
    for m in db.scalars(select(Member).where(Member.project_id == project_id)).all():
        db.delete(m)
    db.delete(project)
    db.commit()
    logger.info("Project deleted: id=%s", project_id)


@router.get("/{project_id}/members", response_model=list[MemberOut])
def list_members(project_id: int, user: dict = Depends(current_user), db: Session = Depends(get_db)):
    _get_project_for(db, project_id, user["id"])
    return db.scalars(select(Member).where(Member.project_id == project_id)).all()


@router.post("/{project_id}/members", response_model=MemberOut, status_code=201)
def add_member(
    project_id: int,
    data: MemberAdd,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, member = _get_project_for(db, project_id, user["id"])
    _require_owner(member)
    if db.get(Member, (project_id, data.user_id)):
        raise HTTPException(409, "User is already a member")
    new_member = Member(project_id=project_id, user_id=data.user_id, role="member")
    db.add(new_member)
    db.commit()
    logger.info("Member added: project=%s user=%s", project_id, data.user_id)
    return new_member


@router.delete("/{project_id}/members/{member_id}", status_code=204)
def remove_member(
    project_id: int,
    member_id: int,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, member = _get_project_for(db, project_id, user["id"])
    _require_owner(member)
    target = db.get(Member, (project_id, member_id))
    if not target:
        raise HTTPException(404, "Member not found")
    if target.role == "owner":
        raise HTTPException(400, "Owner cannot be removed")
    db.delete(target)
    db.commit()


# Внутренний эндпоинт для других сервисов (task-service). Gateway его не проксирует.
@internal.get("/projects/{project_id}/members/{user_id}", response_model=MemberOut)
def check_membership(project_id: int, user_id: int, db: Session = Depends(get_db)):
    member = db.get(Member, (project_id, user_id))
    if not member:
        raise HTTPException(404, "Not a member")
    return member