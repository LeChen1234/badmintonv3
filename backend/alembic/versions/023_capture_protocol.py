"""add capture and annotation protocol metadata

Revision ID: 023_capture_protocol
Revises: 022_match_format
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "023_capture_protocol"
down_revision: Union[str, None] = "022_match_format"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("task_batches") as batch_op:
        batch_op.add_column(sa.Column("capture_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("task_batches") as batch_op:
        batch_op.drop_column("capture_metadata")
