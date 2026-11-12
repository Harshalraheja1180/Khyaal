from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.base import utc_now
from app.db.session import get_db
from app.models.entities import Notification, User
from app.schemas.api import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    limit: int = Query(default=25, ge=1, le=50),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Notification]:
    return list(db.scalars(
        select(Notification)
        .where(Notification.user_id == current.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
    ).all())


@router.get("/unread-count")
def unread_count(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, int]:
    count = db.scalar(select(func.count(Notification.id)).where(
        Notification.user_id == current.id,
        Notification.is_read.is_(False),
    )) or 0
    return {"unread_count": count}


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: UUID,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Notification:
    notification = db.scalar(select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == current.id,
    ))
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = utc_now()
        notification.status = "read"
        db.commit()
        db.refresh(notification)
    return notification


@router.post("/read-all")
def mark_all_notifications_read(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, int]:
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == current.id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=utc_now(), status="read")
    )
    db.commit()
    return {"updated_count": result.rowcount or 0}
