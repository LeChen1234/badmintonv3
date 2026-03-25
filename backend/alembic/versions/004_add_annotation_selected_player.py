"""reserved revision for annotation player relation

Revision ID: 004
Revises: 003
Create Date: 2026-03-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op reserved revision to keep migration chain stable.
    return


def downgrade() -> None:
    return
