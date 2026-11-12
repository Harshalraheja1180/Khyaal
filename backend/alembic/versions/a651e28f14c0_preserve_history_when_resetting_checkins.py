"""allow an authorized reset without deleting a daily result

Revision ID: a651e28f14c0
Revises: 4d237a8a91cf
Create Date: 2026-09-28 12:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a651e28f14c0"
down_revision: Union[str, None] = "4d237a8a91cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("wellbeing_checkins")}
    if "reset_at" not in columns:
        op.add_column("wellbeing_checkins", sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True))

    constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("wellbeing_checkins")}
    if "uq_wellbeing_dependent_date" in constraints:
        op.drop_constraint("uq_wellbeing_dependent_date", "wellbeing_checkins", type_="unique")

    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("wellbeing_checkins")}
    if "uq_wellbeing_dependent_date_active" not in indexes:
        op.create_index(
            "uq_wellbeing_dependent_date_active",
            "wellbeing_checkins",
            ["dependent_id", "checkin_date"],
            unique=True,
            postgresql_where=sa.text("reset_at IS NULL"),
        )


def downgrade() -> None:
    # Reset entries remain in history; release the date they had reserved before restoring the old constraint.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("wellbeing_checkins")}
    indexes = {index["name"] for index in inspector.get_indexes("wellbeing_checkins")}
    if "reset_at" in columns:
        op.execute(sa.text("UPDATE wellbeing_checkins SET checkin_date = NULL WHERE reset_at IS NOT NULL"))
    if "uq_wellbeing_dependent_date_active" in indexes:
        op.drop_index("uq_wellbeing_dependent_date_active", table_name="wellbeing_checkins")
    if "reset_at" in columns:
        op.drop_column("wellbeing_checkins", "reset_at")
    inspector = sa.inspect(bind)
    constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("wellbeing_checkins")}
    if "uq_wellbeing_dependent_date" not in constraints:
        op.create_unique_constraint(
            "uq_wellbeing_dependent_date",
            "wellbeing_checkins",
            ["dependent_id", "checkin_date"],
        )
