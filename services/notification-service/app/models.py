from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _now():
    return datetime.now(timezone.utc)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)  # кому адресовано
    type: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(String(500))
    task_id: Mapped[int | None] = mapped_column(nullable=True)
    project_id: Mapped[int | None] = mapped_column(nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)