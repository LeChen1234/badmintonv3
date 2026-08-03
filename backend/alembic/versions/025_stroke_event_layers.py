"""add four-layer stroke event annotations

Revision ID: 025_stroke_event_layers
Revises: 024_temporal_segments
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "025_stroke_event_layers"
down_revision: Union[str, None] = "024_temporal_segments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("temporal_segments") as batch_op:
        batch_op.add_column(sa.Column("context", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("execution", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("outcome", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("evidence", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("temporal_segments") as batch_op:
        batch_op.drop_column("evidence")
        batch_op.drop_column("outcome")
        batch_op.drop_column("execution")
        batch_op.drop_column("context")
