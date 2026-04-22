"""add is_super_admin column to users

Revision ID: 010
Revises: 009_add_box_to_annotations
Create Date: 2026-04-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009_add_box_to_annotations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}
    if "is_super_admin" not in columns:
        op.add_column(
            "users",
            sa.Column("is_super_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}
    if "is_super_admin" in columns:
        op.drop_column("users", "is_super_admin")
