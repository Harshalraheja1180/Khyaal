"""add scored daily check-ins and normalize games to casual formats

Revision ID: 4d237a8a91cf
Revises: bac8432e6ce1
Create Date: 2026-09-28 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d237a8a91cf"
down_revision: Union[str, None] = "bac8432e6ce1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("wellbeing_checkins", sa.Column("checkin_date", sa.Date(), nullable=True))
    op.add_column("wellbeing_checkins", sa.Column("overall_score", sa.Integer(), nullable=True))
    op.add_column("wellbeing_checkins", sa.Column("overall_category", sa.String(length=40), nullable=True))
    op.add_column("wellbeing_checkins", sa.Column("category_scores", sa.JSON(), nullable=True))
    op.add_column("wellbeing_checkins", sa.Column("summary", sa.Text(), nullable=True))
    op.create_unique_constraint(
        "uq_wellbeing_dependent_date",
        "wellbeing_checkins",
        ["dependent_id", "checkin_date"],
    )

    # Preserve past game sessions, while replacing personal-photo and familiar-place games.
    op.execute(sa.text("""
        UPDATE games
        SET game_type = CASE lower(game_type)
            WHEN 'sequence_recall' THEN 'sequence_memory'
            WHEN 'pattern_recall' THEN 'pattern_memory'
            WHEN 'tile_recall' THEN 'tile_memory'
            WHEN 'odd_pattern_out' THEN 'odd_one_out'
            WHEN 'family_match' THEN 'matching_pairs'
            WHEN 'familiar_place' THEN 'matching_pairs'
            WHEN 'object_match' THEN 'matching_pairs'
            WHEN 'picture_match' THEN 'matching_pairs'
            WHEN 'sequence_memory' THEN 'sequence_memory'
            WHEN 'tile_memory' THEN 'tile_memory'
            WHEN 'pattern_memory' THEN 'pattern_memory'
            WHEN 'matching_pairs' THEN 'matching_pairs'
            WHEN 'odd_one_out' THEN 'odd_one_out'
            ELSE 'matching_pairs'
        END,
        title = CASE lower(game_type)
            WHEN 'sequence_recall' THEN 'Sequence Memory'
            WHEN 'pattern_recall' THEN 'Pattern Memory'
            WHEN 'tile_recall' THEN 'Tile Memory'
            WHEN 'odd_pattern_out' THEN 'Odd One Out'
            WHEN 'sequence_memory' THEN 'Sequence Memory'
            WHEN 'tile_memory' THEN 'Tile Memory'
            WHEN 'pattern_memory' THEN 'Pattern Memory'
            WHEN 'matching_pairs' THEN 'Matching Pairs'
            WHEN 'odd_one_out' THEN 'Odd One Out'
            ELSE 'Matching Pairs'
        END,
        configuration = '{"difficulty":"gentle","kind":"general"}'::json
    """))


def downgrade() -> None:
    op.drop_constraint("uq_wellbeing_dependent_date", "wellbeing_checkins", type_="unique")
    op.drop_column("wellbeing_checkins", "summary")
    op.drop_column("wellbeing_checkins", "category_scores")
    op.drop_column("wellbeing_checkins", "overall_category")
    op.drop_column("wellbeing_checkins", "overall_score")
    op.drop_column("wellbeing_checkins", "checkin_date")
