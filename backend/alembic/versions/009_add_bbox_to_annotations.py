"""add box fields to frame_annotations

Revision ID: 009_add_box_to_annotations
Revises: 008_add_player_profile_columns
Create Date: 2026-03-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "009_add_box_to_annotations"
down_revision: Union[str, None] = "008_add_player_profile_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns(table_name)}
    return column_name in columns


def upgrade() -> None:
    with op.batch_alter_table("frame_annotations") as batch_op:
        if not _has_column("frame_annotations", "box_x"):
            batch_op.add_column(sa.Column("box_x", sa.Float(), nullable=True))
        if not _has_column("frame_annotations", "box_y"):
            batch_op.add_column(sa.Column("box_y", sa.Float(), nullable=True))
        if not _has_column("frame_annotations", "box_w"):
            batch_op.add_column(sa.Column("box_w", sa.Float(), nullable=True))
        if not _has_column("frame_annotations", "box_h"):
            batch_op.add_column(sa.Column("box_h", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("frame_annotations") as batch_op:
        if _has_column("frame_annotations", "box_h"):
            batch_op.drop_column("box_h")
        if _has_column("frame_annotations", "box_w"):
            batch_op.drop_column("box_w")
        if _has_column("frame_annotations", "box_y"):
            batch_op.drop_column("box_y")
        if _has_column("frame_annotations", "box_x"):
            batch_op.drop_column("box_x")
