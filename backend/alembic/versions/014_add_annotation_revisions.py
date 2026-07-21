"""add append-only annotation revision events

Revision ID: 014_add_annotation_revisions
Revises: 013_add_annotation_provenance
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "014_add_annotation_revisions"
down_revision: Union[str, None] = "013_add_annotation_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "annotation_revisions" in inspector.get_table_names():
        return
    op.create_table(
        "annotation_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("annotation_id", sa.Integer(), sa.ForeignKey("frame_annotations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("editor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="manual_edit"),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("before_snapshot", sa.JSON(), nullable=False),
        sa.Column("after_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_annotation_revisions_annotation_id", "annotation_revisions", ["annotation_id"])
    op.create_index("ix_annotation_revisions_editor_id", "annotation_revisions", ["editor_id"])


def downgrade() -> None:
    op.drop_index("ix_annotation_revisions_editor_id", table_name="annotation_revisions")
    op.drop_index("ix_annotation_revisions_annotation_id", table_name="annotation_revisions")
    op.drop_table("annotation_revisions")
