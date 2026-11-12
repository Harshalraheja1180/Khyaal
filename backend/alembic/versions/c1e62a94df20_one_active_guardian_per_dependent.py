"""enforce one active guardian per dependent and quarantine legacy conflicts

Revision ID: c1e62a94df20
Revises: b92f3ac81d20
Create Date: 2026-10-09 10:00:00.000000
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1e62a94df20"
down_revision: Union[str, None] = "b92f3ac81d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    bind = op.get_bind()
    conflicts = bind.execute(sa.text("""
        SELECT dependent_id
        FROM guardian_links
        WHERE status = 'active'
        GROUP BY dependent_id
        HAVING count(*) > 1
        ORDER BY dependent_id
    """)).scalars().all()

    for dependent_id in conflicts:
        links = bind.execute(sa.text("""
            SELECT id, guardian_id
            FROM guardian_links
            WHERE dependent_id = :dependent_id AND status = 'active'
            ORDER BY created_at, id
        """), {"dependent_id": dependent_id}).mappings().all()
        link_ids = [str(link["id"]) for link in links]
        guardian_ids = sorted({link["guardian_id"] for link in links}, key=str)
        logger.warning(
            "Quarantining multiple active guardian links without deleting data: dependent_id=%s link_ids=%s",
            dependent_id,
            link_ids,
        )

        now = datetime.now(timezone.utc)
        for link in links:
            bind.execute(sa.text("""
                UPDATE guardian_links
                SET status = 'conflict', updated_at = :now
                WHERE id = :link_id
            """), {"now": now, "link_id": link["id"]})
            bind.execute(sa.text("""
                INSERT INTO audit_logs
                    (id, actor_id, action, resource_type, resource_id, dependent_id, outcome, occurred_at)
                VALUES
                    (:id, NULL, 'guardian_link.conflict_quarantined', 'guardian_link', :resource_id, :dependent_id, 'review', :occurred_at)
            """), {
                "id": uuid.uuid4(),
                "resource_id": str(link["id"]),
                "dependent_id": dependent_id,
                "occurred_at": now,
            })

        recipients = [(dependent_id, links[0]["id"], "dependent")]
        recipients.extend((guardian_id, next(link["id"] for link in links if link["guardian_id"] == guardian_id), "guardian") for guardian_id in guardian_ids)
        for recipient_id, link_id, recipient_role in recipients:
            if recipient_role == "dependent":
                title = "Care connections need review"
                message = "Multiple active guardian connections were found. For privacy, these connections are paused. Ask the guardian you trust to send a new request after you decide who should have access."
            else:
                title = "Care connection paused for review"
                message = "Multiple guardian connections were found for a dependent account. For privacy, access is paused until the dependent resolves the connections."
            notification_type = "guardian_link.conflict_quarantined"
            bind.execute(sa.text("""
                INSERT INTO notifications
                    (id, user_id, notification_type, title, message, is_read, read_at,
                     guardian_link_id, category, payload, status, created_at)
                VALUES
                    (:id, :user_id, :notification_type, :title, :message, false, NULL,
                     :guardian_link_id, :category, CAST(:payload AS json), 'unread', :created_at)
            """), {
                "id": uuid.uuid4(),
                "user_id": recipient_id,
                "notification_type": notification_type,
                "title": title,
                "message": message,
                "guardian_link_id": link_id,
                "category": notification_type[:32],
                "payload": json.dumps({"title": title, "message": message, "guardian_link_id": str(link_id)}),
                "created_at": now,
            })

    op.create_index(
        "uq_guardian_links_one_active_per_dependent",
        "guardian_links",
        ["dependent_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    # Keep quarantined rows in the conflict state; reviving them could restore
    # a multi-guardian privacy exposure. Dropping the constraint is safe.
    op.drop_index("uq_guardian_links_one_active_per_dependent", table_name="guardian_links")
