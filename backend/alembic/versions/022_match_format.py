"""classify singles and doubles matches

Revision ID: 022_match_format
Revises: 021_expert_triage_workflow
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "022_match_format"
down_revision: Union[str, None] = "021_expert_triage_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("task_batches") as batch_op:
        batch_op.add_column(sa.Column("match_format", sa.String(16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("task_batches") as batch_op:
        batch_op.drop_column("match_format")
