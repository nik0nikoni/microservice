from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _now():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    owner_id: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Member(Base):
    __tablename__ = "members"

    # составной ключ: один пользователь не может быть в проекте дважды
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), primary_key=True, autoincrement=False
    )
    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    role: Mapped[str] = mapped_column(String(20), default="member")  # owner | member