"""add player detail columns

Revision ID: 008_add_player_profile_columns
Revises: 007_add_unique_constraints_player
Create Date: 2026-03-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008_add_player_profile_columns"
down_revision: Union[str, None] = "007_add_unique_constraints_player"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns(table_name)}
    return column_name in columns


def upgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        if not _has_column("players", "gender"):
            batch_op.add_column(sa.Column("gender", sa.String(length=16), nullable=True))
        if not _has_column("players", "age"):
            batch_op.add_column(sa.Column("age", sa.Integer(), nullable=True))
        if not _has_column("players", "height_cm"):
            batch_op.add_column(sa.Column("height_cm", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        if _has_column("players", "height_cm"):
            batch_op.drop_column("height_cm")
        if _has_column("players", "age"):
            batch_op.drop_column("age")
        if _has_column("players", "gender"):
            batch_op.drop_column("gender")
