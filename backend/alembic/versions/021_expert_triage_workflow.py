"""separate student coarse annotation from expert judgment

Revision ID: 021_expert_triage_workflow
Revises: 020_video_identity_frame_timestamps
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "021_expert_triage_workflow"
down_revision: Union[str, None] = "020_video_identity_frame_timestamps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("frame_annotations") as batch_op:
        batch_op.add_column(sa.Column("workflow_stage", sa.String(32), nullable=False, server_default="student_coarse"))
        batch_op.add_column(sa.Column("expert_review_required", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("expert_review_reasons", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("expert_reviewed_by", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("expert_reviewed_at", sa.DateTime(), nullable=True))
        batch_op.create_foreign_key("fk_annotation_expert_reviewer", "users", ["expert_reviewed_by"], ["id"])
    op.create_index("ix_annotations_expert_queue", "frame_annotations", ["expert_review_required", "workflow_stage"])


def downgrade() -> None:
    op.drop_index("ix_annotations_expert_queue", table_name="frame_annotations")
    with op.batch_alter_table("frame_annotations") as batch_op:
        batch_op.drop_constraint("fk_annotation_expert_reviewer", type_="foreignkey")
        batch_op.drop_column("expert_reviewed_at")
        batch_op.drop_column("expert_reviewed_by")
        batch_op.drop_column("expert_review_reasons")
        batch_op.drop_column("expert_review_required")
        batch_op.drop_column("workflow_stage")
