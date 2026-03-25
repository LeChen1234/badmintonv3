"""add task metadata columns

Revision ID: 003
Revises: 002
Create Date: 2026-03-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("task_batches") as batch_op:
        batch_op.add_column(sa.Column("match_name", sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column("match_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("metadata_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("metadata_confirmed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("task_batches") as batch_op:
        batch_op.drop_column("metadata_confirmed_at")
        batch_op.drop_column("metadata_confirmed")
        batch_op.drop_column("match_date")
        batch_op.drop_column("match_name")
