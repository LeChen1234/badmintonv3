"""add_unique_constraints_and_player_table

Revision ID: 007_add_unique_constraints_player
Revises: 006_add_uuid_columns
Create Date: 2026-03-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "007_add_unique_constraints_player"
down_revision = "006_add_uuid_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create players table
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(36), nullable=False),
        sa.Column("task_batch_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("gender", sa.String(16), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("height_cm", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["task_batch_id"], ["task_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid", name="ux_players_uuid"),
    )
    op.create_index("ix_players_uuid", "players", ["uuid"], unique=True)
    op.create_index("ix_players_task_batch_id", "players", ["task_batch_id"])

    # Add selected_player_id to frame_annotations
    op.add_column(
        "frame_annotations",
        sa.Column("selected_player_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_frame_annotations_selected_player_id_players",
        "frame_annotations",
        "players",
        ["selected_player_id"],
        ["id"],
    )

    # Add composite unique index for batch_frames
    op.create_unique_constraint(
        "ux_batch_frames_task_batch_frame",
        "batch_frames",
        ["task_batch_id", "frame_index"],
    )

    # Add composite unique index for frame_annotations (per annotator)
    op.create_unique_constraint(
        "ux_frame_annotations_task_batch_frame_annotator",
        "frame_annotations",
        ["task_batch_id", "frame_index", "annotator_id"],
    )

    # Add composite index for fast lookups
    op.create_index(
        "ix_frame_annotations_task_batch_frame",
        "frame_annotations",
        ["task_batch_id", "frame_index"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_frame_annotations_task_batch_frame",
        table_name="frame_annotations",
    )
    op.drop_constraint(
        "ux_frame_annotations_task_batch_frame_annotator",
        "frame_annotations",
        type_="unique",
    )
    op.drop_constraint(
        "ux_batch_frames_task_batch_frame",
        "batch_frames",
        type_="unique",
    )
    op.drop_constraint(
        "fk_frame_annotations_selected_player_id_players",
        "frame_annotations",
        type_="foreignkey",
    )
    op.drop_column("frame_annotations", "selected_player_id")
    op.drop_index("ix_players_task_batch_id", table_name="players")
    op.drop_index("ix_players_uuid", table_name="players")
    op.drop_table("players")
