"""add expert adjudication records

Revision ID: 017_add_adjudication_records
Revises: 016_add_secondary_annotator
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "017_add_adjudication_records"
down_revision: Union[str, None] = "016_add_secondary_annotator"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "adjudication_records" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "adjudication_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_batch_id", sa.Integer(), sa.ForeignKey("task_batches.id"), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("selected_player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=True),
        sa.Column("expert_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("winner_annotation_id", sa.Integer(), sa.ForeignKey("frame_annotations.id"), nullable=False),
        sa.Column("candidate_annotation_ids", sa.JSON(), nullable=False),
        sa.Column("disagreement_snapshot", sa.JSON(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_adjudication_records_task_batch_id", "adjudication_records", ["task_batch_id"])
    op.create_index("ix_adjudication_records_winner_annotation_id", "adjudication_records", ["winner_annotation_id"])


def downgrade() -> None:
    op.drop_index("ix_adjudication_records_winner_annotation_id", table_name="adjudication_records")
    op.drop_index("ix_adjudication_records_task_batch_id", table_name="adjudication_records")
    op.drop_table("adjudication_records")
