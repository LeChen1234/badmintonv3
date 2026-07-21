"""add annotation provenance and interaction measurements

Revision ID: 013_add_annotation_provenance
Revises: 012_add_contact_annotation
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "013_add_annotation_provenance"
down_revision: Union[str, None] = "012_add_contact_annotation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("frame_annotations")}
    with op.batch_alter_table("frame_annotations") as batch_op:
        if "taxonomy_version" not in existing:
            batch_op.add_column(sa.Column("taxonomy_version", sa.String(32), nullable=True))
        if "assist_metadata" not in existing:
            batch_op.add_column(sa.Column("assist_metadata", sa.JSON(), nullable=True))
        if "assist_accepted" not in existing:
            batch_op.add_column(sa.Column("assist_accepted", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "annotation_duration_ms" not in existing:
            batch_op.add_column(sa.Column("annotation_duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("frame_annotations") as batch_op:
        batch_op.drop_column("annotation_duration_ms")
        batch_op.drop_column("assist_accepted")
        batch_op.drop_column("assist_metadata")
        batch_op.drop_column("taxonomy_version")
