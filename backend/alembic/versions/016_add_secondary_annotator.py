"""add blind secondary annotator slot

Revision ID: 016_add_secondary_annotator
Revises: 015_add_subject_code
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "016_add_secondary_annotator"
down_revision: Union[str, None] = "015_add_subject_code"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("task_batches")}
    if "secondary_assigned_to" not in columns:
        with op.batch_alter_table("task_batches") as batch_op:
            batch_op.add_column(sa.Column("secondary_assigned_to", sa.Integer(), nullable=True))
            batch_op.create_foreign_key("fk_task_batches_secondary_assigned_to_users", "users", ["secondary_assigned_to"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("task_batches") as batch_op:
        batch_op.drop_constraint("fk_task_batches_secondary_assigned_to_users", type_="foreignkey")
        batch_op.drop_column("secondary_assigned_to")
