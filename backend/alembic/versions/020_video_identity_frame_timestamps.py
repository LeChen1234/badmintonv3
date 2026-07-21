"""video identity, frame timestamps and per-player frame annotations

Revision ID: 020_video_identity_frame_timestamps
Revises: 019_add_selection_metadata
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "020_video_identity_frame_timestamps"
down_revision: Union[str, None] = "019_add_selection_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("task_batches") as batch_op:
        batch_op.add_column(sa.Column("video_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("video_sha256", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("video_filename", sa.String(512), nullable=True))
        batch_op.create_unique_constraint("ux_task_batches_video_id", ["video_id"])
        batch_op.create_unique_constraint("ux_task_batches_video_sha256", ["video_sha256"])
    with op.batch_alter_table("batch_frames") as batch_op:
        batch_op.add_column(sa.Column("timestamp_ms", sa.BigInteger(), nullable=False, server_default="0"))
    annotation_constraints = {
        item.get("name") for item in sa.inspect(op.get_bind()).get_unique_constraints("frame_annotations")
    }
    with op.batch_alter_table("frame_annotations") as batch_op:
        if "ux_frame_annotations_task_batch_frame_annotator" in annotation_constraints:
            batch_op.drop_constraint("ux_frame_annotations_task_batch_frame_annotator", type_="unique")
        batch_op.create_unique_constraint(
            "ux_frame_annotations_batch_frame_annotator_player",
            ["task_batch_id", "frame_index", "annotator_id", "selected_player_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("frame_annotations") as batch_op:
        batch_op.drop_constraint("ux_frame_annotations_batch_frame_annotator_player", type_="unique")
        batch_op.create_unique_constraint(
            "ux_frame_annotations_task_batch_frame_annotator",
            ["task_batch_id", "frame_index", "annotator_id"],
        )
    with op.batch_alter_table("batch_frames") as batch_op:
        batch_op.drop_column("timestamp_ms")
    with op.batch_alter_table("task_batches") as batch_op:
        batch_op.drop_constraint("ux_task_batches_video_sha256", type_="unique")
        batch_op.drop_constraint("ux_task_batches_video_id", type_="unique")
        batch_op.drop_column("video_filename")
        batch_op.drop_column("video_sha256")
        batch_op.drop_column("video_id")
