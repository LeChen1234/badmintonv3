"""add media process status columns to task_batches

Revision ID: 002
Revises: 001
Create Date: 2026-03-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("task_batches") as batch_op:
        batch_op.add_column(sa.Column("media_process_status", sa.String(length=32), nullable=False, server_default="idle"))
        batch_op.add_column(sa.Column("media_process_message", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("media_process_started_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("media_process_finished_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("task_batches") as batch_op:
        batch_op.drop_column("media_process_finished_at")
        batch_op.drop_column("media_process_started_at")
        batch_op.drop_column("media_process_message")
        batch_op.drop_column("media_process_status")
