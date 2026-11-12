from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.models.entities import Notification


def create_notification(
    db: Session,
    *,
    recipient_id: UUID,
    notification_type: str,
    title: str,
    message: str,
    guardian_link_id: UUID | None = None,
) -> Notification:
    """Persist a private in-app notification for its recipient."""
    notification = Notification(
        user_id=recipient_id,
        notification_type=notification_type,
        title=title,
        message=message,
        is_read=False,
        guardian_link_id=guardian_link_id,
        category=notification_type[:32],
        payload={"title": title, "message": message, "guardian_link_id": str(guardian_link_id) if guardian_link_id else None},
        status="unread",
    )
    db.add(notification)
    return notification


def mark_link_invitation_read(db: Session, *, recipient_id: UUID, link_id: UUID) -> None:
    invitations = db.scalars(select(Notification).where(
        Notification.user_id == recipient_id,
        Notification.guardian_link_id == link_id,
        Notification.notification_type == "guardian_link.invited",
        Notification.is_read.is_(False),
    )).all()
    now = utc_now()
    for notification in invitations:
        notification.is_read = True
        notification.read_at = now
        notification.status = "read"
