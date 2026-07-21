"""add active learning feedback rounds

Revision ID: 018_add_active_learning_rounds
Revises: 017_add_adjudication_records
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "018_add_active_learning_rounds"
down_revision: Union[str, None] = "017_add_adjudication_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "active_learning_rounds" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "active_learning_rounds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.String(64), nullable=False),
        sa.Column("model_version", sa.String(128), nullable=False),
        sa.Column("selection_strategy", sa.String(64), nullable=False),
        sa.Column("annotation_count", sa.Integer(), nullable=False),
        sa.Column("annotation_hours", sa.Float(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("component_gains", sa.JSON(), nullable=False),
        sa.Column("marginal_utility", sa.JSON(), nullable=False),
        sa.Column("recommended_weights", sa.JSON(), nullable=False),
        sa.Column("stop_recommended", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "round_index", name="ux_active_round_project_index"),
    )
    op.create_index("ix_active_learning_rounds_project_id", "active_learning_rounds", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_active_learning_rounds_project_id", table_name="active_learning_rounds")
    op.drop_table("active_learning_rounds")
