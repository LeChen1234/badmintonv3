"""add cross-match pseudonymous subject identity

Revision ID: 015_add_subject_code
Revises: 014_add_annotation_revisions
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015_add_subject_code"
down_revision: Union[str, None] = "014_add_annotation_revisions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("players")}
    if "subject_code" not in columns:
        with op.batch_alter_table("players") as batch_op:
            batch_op.add_column(sa.Column("subject_code", sa.String(64), nullable=True))
            batch_op.create_index("ix_players_subject_code", ["subject_code"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_index("ix_players_subject_code")
        batch_op.drop_column("subject_code")
