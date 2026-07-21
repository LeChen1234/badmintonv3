"""persist frame-selection provenance

Revision ID: 019_add_selection_metadata
Revises: 018_add_active_learning_rounds
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "019_add_selection_metadata"
down_revision: Union[str, None] = "018_add_active_learning_rounds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("task_batches")}
    if "selection_metadata" not in columns:
        with op.batch_alter_table("task_batches") as batch_op:
            batch_op.add_column(sa.Column("selection_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("task_batches") as batch_op:
        batch_op.drop_column("selection_metadata")
