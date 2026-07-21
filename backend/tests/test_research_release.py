import unittest

from app.services.research_release_service import build_release, canonical_fingerprint


PROTOCOL = {
    "version": "test-v1",
    "split_seed": "fixed",
    "group_key_priority": ["match_uuid", "task_batch_uuid"],
    "splits": {"train": 0.7, "validation": 0.15, "test": 0.15},
    "release_requirements": {"minimum_matches": 1, "minimum_action_classes": 1, "minimum_pose_coverage": 0},
}


class ResearchReleaseTests(unittest.TestCase):
    def test_fingerprint_is_stable_for_key_order(self):
        self.assertEqual(canonical_fingerprint([{"b": 2, "a": 1}]), canonical_fingerprint([{"a": 1, "b": 2}]))

    def test_same_match_never_crosses_splits(self):
        records = [
            {"annotation_id": index, "match_uuid": "same-match", "action_type": "smash", "keypoints": []}
            for index in range(5)
        ]
        released, manifest = build_release(records, "project", PROTOCOL)
        self.assertEqual(len({record["research_split"] for record in released}), 1)
        self.assertEqual(manifest["group_count"], 1)

    def test_release_without_group_identity_fails_gate(self):
        released, manifest = build_release([{"annotation_id": 1, "action_type": "smash"}], "project", PROTOCOL)
        self.assertEqual(released[0]["research_group"]["key"], "missing")
        self.assertFalse(manifest["quality_gates"]["stable_group_identity"])
        self.assertFalse(manifest["release_ready"])

    def test_same_subject_across_matches_stays_in_one_split(self):
        protocol = dict(PROTOCOL, group_key_priority=["subject_code", "match_uuid"])
        records = [
            {"annotation_id": 1, "subject_code": "S1", "match_uuid": "M1", "action_type": "smash"},
            {"annotation_id": 2, "subject_code": "S1", "match_uuid": "M2", "action_type": "smash"},
        ]
        released, _ = build_release(records, "project", protocol)
        self.assertEqual(len({record["research_split"] for record in released}), 1)


if __name__ == "__main__":
    unittest.main()
