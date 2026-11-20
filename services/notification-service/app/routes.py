from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .deps import current_user
from .models import Notification
from .schemas import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Notification).where(Notification.user_id == user["id"])
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.id.desc())
    return db.scalars(stmt).all()


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    notification = db.get(Notification, notification_id)
    # чужое уведомление выглядит как несуществующее
    if not notification or notification.user_id != user["id"]:
        raise HTTPException(404, "Notification not found")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification