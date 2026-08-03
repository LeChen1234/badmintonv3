import csv
import io
from types import SimpleNamespace

from app.api.export import _capture_group_fields, _records_to_csv


def test_capture_group_ids_are_scoped_to_session():
    batch = SimpleNamespace(
        capture_metadata={
            "capture_session_id": "SESSION-1",
            "bridge_view_id": "BRIDGE-1",
            "repetition_group_id": "REPEAT-1",
        }
    )
    fields = _capture_group_fields(batch)
    assert fields["bridge_view_id"] == "SESSION-1:BRIDGE-1"
    assert fields["repetition_group_id"] == "SESSION-1:REPEAT-1"


def test_csv_capture_columns_remain_aligned():
    value = _records_to_csv([
        {
            "task_batch_id": 1,
            "video_id": "V1",
            "capture_metadata": {
                "capture_mode": "controlled_training",
                "annotation_goal": "technique_quality",
                "camera_view": "left",
                "capture_session_id": "SESSION-1",
                "bridge_view_id": "BRIDGE-1",
                "repetition_group_id": "REPEAT-1",
                "target_action": "smash",
                "recording_design": "prescribed_standard",
                "recording_fps": 60,
                "feed_method": "coach",
            },
            "frame_index": 1,
        }
    ])
    rows = list(csv.reader(io.StringIO(value)))
    assert len(rows) == 2
    assert len(rows[0]) == len(rows[1])
    record = dict(zip(rows[0], rows[1]))
    assert record["recording_design"] == "prescribed_standard"
    assert record["bridge_view_id"] == "BRIDGE-1"
