"""initial schema — users, projects, task_batches, review_records, audit_logs

Revision ID: 001
Revises:
Create Date: 2026-02-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("username", sa.String(64), unique=True, index=True, nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "expert", "leader", "student", name="userrole"),
            nullable=False,
            server_default="student",
        ),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("ls_user_id", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.String(1024), nullable=True),
        sa.Column("ls_project_id", sa.Integer, nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "task_batches",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("action_category", sa.String(64), nullable=True),
        sa.Column("assigned_to", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "annotating", "self_review",
                "leader_review", "expert_review", "locked",
                name="taskstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("frame_start", sa.Integer, nullable=True),
        sa.Column("frame_end", sa.Integer, nullable=True),
        sa.Column("total_frames", sa.Integer, server_default=sa.text("0")),
        sa.Column("completed_frames", sa.Integer, server_default=sa.text("0")),
        sa.Column("deadline", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "review_records",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("task_batch_id", sa.Integer, sa.ForeignKey("task_batches.id"), nullable=False),
        sa.Column("reviewer_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "review_level",
            sa.Enum("self", "leader", "expert", name="reviewlevel"),
            nullable=False,
        ),
        sa.Column(
            "result",
            sa.Enum("pass", "reject", name="reviewresult"),
            nullable=False,
        ),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("review_records")
    op.drop_table("task_batches")
    op.drop_table("projects")
    op.drop_table("users")
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="taskstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="reviewlevel").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="reviewresult").drop(op.get_bind(), checkfirst=True)
