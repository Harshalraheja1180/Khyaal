"""add persistent relationship notifications and decline timestamps

Revision ID: b92f3ac81d20
Revises: a651e28f14c0
Create Date: 2026-10-08 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b92f3ac81d20"
down_revision: Union[str, None] = "a651e28f14c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("guardian_links", sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True))

    # notifications already existed as a generic in-app event table. Extend it
    # in place so existing development data and references remain intact.
    op.add_column("notifications", sa.Column("notification_type", sa.String(length=64), nullable=True))
    op.add_column("notifications", sa.Column("title", sa.String(length=160), nullable=True))
    op.add_column("notifications", sa.Column("message", sa.Text(), nullable=True))
    op.add_column("notifications", sa.Column("is_read", sa.Boolean(), nullable=True))
    op.add_column("notifications", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notifications", sa.Column("guardian_link_id", sa.Uuid(), nullable=True))

    op.execute(sa.text("""
        UPDATE notifications
        SET notification_type = COALESCE(NULLIF(category, ''), 'system.notice'),
            title = COALESCE(NULLIF(payload ->> 'title', ''), 'MemoryCare update'),
            message = COALESCE(NULLIF(payload ->> 'message', ''), 'There is an update in your MemoryCare account.'),
            is_read = (status = 'read')
    """))

    op.alter_column("notifications", "notification_type", nullable=False)
    op.alter_column("notifications", "title", nullable=False)
    op.alter_column("notifications", "message", nullable=False)
    op.alter_column("notifications", "is_read", nullable=False)
    op.create_foreign_key(
        "fk_notifications_guardian_link_id_guardian_links",
        "notifications", "guardian_links", ["guardian_link_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])
    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "is_read"])
    op.create_index("ix_notifications_guardian_link_id", "notifications", ["guardian_link_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_guardian_link_id", table_name="notifications")
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_constraint("fk_notifications_guardian_link_id_guardian_links", "notifications", type_="foreignkey")
    op.drop_column("notifications", "guardian_link_id")
    op.drop_column("notifications", "read_at")
    op.drop_column("notifications", "is_read")
    op.drop_column("notifications", "message")
    op.drop_column("notifications", "title")
    op.drop_column("notifications", "notification_type")
    op.drop_column("guardian_links", "declined_at")
