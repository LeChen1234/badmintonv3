import unittest
from types import SimpleNamespace

from app.services.agreement_service import build_agreement_report


def annotation(annotator, frame, action="smash", dx=0.0):
    return SimpleNamespace(
        annotator_id=annotator,
        frame_index=frame,
        selected_player_id=1,
        action_type=action,
        action_phase="contact",
        quality_rating="standard",
        is_contact_event=True,
        box_w=100,
        box_h=100,
        keypoints=[{"name": "left_wrist", "x": 50 + dx, "y": 50, "visibility": 2}],
    )


class AgreementServiceTests(unittest.TestCase):
    def test_perfect_pair_has_perfect_observed_agreement_and_pck(self):
        report = build_agreement_report([annotation(1, 1), annotation(2, 1)], minimum_items=1)
        self.assertEqual(report["categorical"]["action_type"]["observed_agreement"], 1.0)
        self.assertEqual(report["keypoints"]["pck"]["0.05"], 1.0)
        self.assertTrue(report["readiness"]["ready"])

    def test_single_annotator_is_not_ready(self):
        report = build_agreement_report([annotation(1, 1)], minimum_items=1)
        self.assertFalse(report["readiness"]["ready"])
        self.assertEqual(report["double_annotated_items"], 0)

    def test_label_disagreement_is_detected(self):
        report = build_agreement_report([annotation(1, 1, "smash"), annotation(2, 1, "clear")], minimum_items=1)
        self.assertEqual(report["categorical"]["action_type"]["observed_agreement"], 0.0)


if __name__ == "__main__":
    unittest.main()
