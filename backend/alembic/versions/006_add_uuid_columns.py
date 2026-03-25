"""add uuid columns for core entities

Revision ID: 006
Revises: 005
Create Date: 2026-03-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("uuid", sa.String(length=36), nullable=True))

    with op.batch_alter_table("task_batches") as batch_op:
        batch_op.add_column(sa.Column("uuid", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("match_uuid", sa.String(length=36), nullable=True))

    with op.batch_alter_table("batch_frames") as batch_op:
        batch_op.add_column(sa.Column("uuid", sa.String(length=36), nullable=True))

    with op.batch_alter_table("frame_annotations") as batch_op:
        batch_op.add_column(sa.Column("uuid", sa.String(length=36), nullable=True))

    op.create_index("ux_projects_uuid", "projects", ["uuid"], unique=True)
    op.create_index("ux_task_batches_uuid", "task_batches", ["uuid"], unique=True)
    op.create_index("ux_task_batches_match_uuid", "task_batches", ["match_uuid"], unique=True)
    op.create_index("ux_batch_frames_uuid", "batch_frames", ["uuid"], unique=True)
    op.create_index("ux_frame_annotations_uuid", "frame_annotations", ["uuid"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_frame_annotations_uuid", table_name="frame_annotations")
    op.drop_index("ux_batch_frames_uuid", table_name="batch_frames")
    op.drop_index("ux_task_batches_match_uuid", table_name="task_batches")
    op.drop_index("ux_task_batches_uuid", table_name="task_batches")
    op.drop_index("ux_projects_uuid", table_name="projects")

    with op.batch_alter_table("frame_annotations") as batch_op:
        batch_op.drop_column("uuid")

    with op.batch_alter_table("batch_frames") as batch_op:
        batch_op.drop_column("uuid")

    with op.batch_alter_table("task_batches") as batch_op:
        batch_op.drop_column("match_uuid")
        batch_op.drop_column("uuid")

    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("uuid")
