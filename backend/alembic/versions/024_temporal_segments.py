"""add continuous temporal action segments

Revision ID: 024_temporal_segments
Revises: 023_capture_protocol
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "024_temporal_segments"
down_revision: Union[str, None] = "023_capture_protocol"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "temporal_segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("task_batch_id", sa.Integer(), nullable=False),
        sa.Column("selected_player_id", sa.Integer(), nullable=False),
        sa.Column("annotator_id", sa.Integer(), nullable=False),
        sa.Column("annotator_name", sa.String(length=128), nullable=False),
        sa.Column("start_frame", sa.Integer(), nullable=False),
        sa.Column("end_frame", sa.Integer(), nullable=False),
        sa.Column("start_timestamp_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("end_timestamp_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("action_phase", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["task_batch_id"], ["task_batches.id"]),
        sa.ForeignKeyConstraint(["selected_player_id"], ["players.id"]),
        sa.ForeignKeyConstraint(["annotator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"]),
        sa.UniqueConstraint("uuid"),
    )
    op.create_index("ix_temporal_segments_id", "temporal_segments", ["id"])
    op.create_index("ix_temporal_segments_uuid", "temporal_segments", ["uuid"], unique=True)
    op.create_index("ix_temporal_segments_task_batch_id", "temporal_segments", ["task_batch_id"])
    op.create_index("ix_temporal_segments_selected_player_id", "temporal_segments", ["selected_player_id"])
    op.create_index("ix_temporal_segments_annotator_id", "temporal_segments", ["annotator_id"])


def downgrade() -> None:
    op.drop_table("temporal_segments")
