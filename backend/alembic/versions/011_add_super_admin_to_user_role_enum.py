"""add super_admin to user role enum

Revision ID: 011_add_super_admin_to_user_role_enum
Revises: 010
Create Date: 2026-04-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "011_add_super_admin_to_user_role_enum"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_USER_ROLE_ENUM = sa.Enum("admin", "expert", "leader", "student", name="userrole")
NEW_USER_ROLE_ENUM = sa.Enum("super_admin", "admin", "expert", "leader", "student", name="userrole")


def _non_pg_role_already_supports_super_admin(bind) -> bool:
    inspector = sa.inspect(bind)
    constraints = inspector.get_check_constraints("users")
    for constraint in constraints:
        sqltext = (constraint.get("sqltext") or "").lower()
        if "role" in sqltext and "super_admin" in sqltext:
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'super_admin'")
        return

    if _non_pg_role_already_supports_super_admin(bind):
        return

    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=OLD_USER_ROLE_ENUM,
            type_=NEW_USER_ROLE_ENUM,
            existing_nullable=False,
            existing_server_default=sa.text("'student'"),
            server_default="student",
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.execute("UPDATE users SET role = 'admin' WHERE role = 'super_admin'")

    if dialect == "postgresql":
        op.execute("ALTER TYPE userrole RENAME TO userrole_old")
        op.execute("CREATE TYPE userrole AS ENUM ('admin', 'expert', 'leader', 'student')")
        op.execute("ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::text::userrole")
        op.execute("DROP TYPE userrole_old")
        return

    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=NEW_USER_ROLE_ENUM,
            type_=OLD_USER_ROLE_ENUM,
            existing_nullable=False,
            existing_server_default=sa.text("'student'"),
            server_default="student",
        )
