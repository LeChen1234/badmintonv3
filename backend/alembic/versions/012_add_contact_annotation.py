"""add contact-centric fields to frame_annotations

Revision ID: 012_add_contact_annotation
Revises: 011_add_super_admin_to_user_role_enum
Create Date: 2026-07-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012_add_contact_annotation"
down_revision: Union[str, None] = "011_add_super_admin_to_user_role_enum"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns(table_name)}
    return column_name in columns


def upgrade() -> None:
    with op.batch_alter_table("frame_annotations") as batch_op:
        if not _has_column("frame_annotations", "is_contact_event"):
            batch_op.add_column(
                sa.Column("is_contact_event", sa.Boolean(), nullable=False, server_default=sa.false())
            )
        if not _has_column("frame_annotations", "contact"):
            batch_op.add_column(sa.Column("contact", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("frame_annotations") as batch_op:
        if _has_column("frame_annotations", "contact"):
            batch_op.drop_column("contact")
        if _has_column("frame_annotations", "is_contact_event"):
            batch_op.drop_column("is_contact_event")
