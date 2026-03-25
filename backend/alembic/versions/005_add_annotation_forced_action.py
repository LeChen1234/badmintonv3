"""add is_forced_action to frame_annotations

Revision ID: 005
Revises: 004
Create Date: 2026-03-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("frame_annotations") as batch_op:
        batch_op.add_column(sa.Column("is_forced_action", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("frame_annotations") as batch_op:
        batch_op.drop_column("is_forced_action")
