import importlib.util
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("quality_report", Path(__file__).parents[2] / "scripts" / "data_quality_report.py")
quality = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quality)


class DataQualityReportTests(unittest.TestCase):
    def record(self, label="smash", group="match-1"):
        return {
            "action_type": label,
            "action_phase": "contact",
            "quality_rating": "standard",
            "match_uuid": group,
            "task_batch_uuid": "batch-1",
            "selected_player_uuid": "player-1",
            "taxonomy_version": "1",
            "annotation_duration_ms": 1200,
            "assist_accepted": True,
            "frame_index": 1,
            "keypoints": [
                {"name": name, "x": 10 + i * 2, "y": 20 + i, "visibility": 2}
                for i, name in enumerate(quality.KEYPOINTS)
            ],
        }

    def test_complete_two_class_export_passes_core_gates(self):
        taxonomy = {
            "actions": [{"value": "smash"}, {"value": "clear"}],
            "phases": [{"value": "contact"}],
            "qualities": [{"value": "standard"}],
        }
        records = [self.record("smash", "m1"), self.record("clear", "m2")]
        report = quality.build_report(records, taxonomy)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["records"]["pose_coverage"], 1.0)

    def test_unknown_label_fails_gate(self):
        taxonomy = {"actions": [{"value": "clear"}], "phases": [{"value": "contact"}], "qualities": [{"value": "standard"}]}
        report = quality.build_report([self.record("invented")], taxonomy)
        self.assertFalse(report["quality_gates"]["no_out_of_taxonomy_labels"])


if __name__ == "__main__":
    unittest.main()
