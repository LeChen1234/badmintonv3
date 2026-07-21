import unittest

from app.services.annotation_assist_service import analyze_pose


def pose(visible=True):
    values = {
        "left_shoulder": (40, 40), "right_shoulder": (60, 40),
        "left_hip": (44, 62), "right_hip": (56, 62),
        "left_elbow": (34, 28), "left_wrist": (38, 10),
        "right_elbow": (66, 50), "right_wrist": (70, 58),
        "left_knee": (44, 78), "left_ankle": (42, 94),
        "right_knee": (58, 78), "right_ankle": (60, 94),
    }
    return [{"name": key, "x": x, "y": y, "visibility": 2 if visible else 0} for key, (x, y) in values.items()]


class AnnotationAssistTests(unittest.TestCase):
    def test_exposes_probability_and_functional_components(self):
        result = analyze_pose(pose())
        self.assertAlmostEqual(sum(result["phase_probabilities"].values()), 1.0, places=3)
        self.assertIn("quality_energy", result["features"])
        for key in ("confidence", "uncertainty", "review_priority"):
            self.assertGreaterEqual(result[key], 0)
            self.assertLessEqual(result[key], 1)

    def test_missing_torso_forces_human_review(self):
        result = analyze_pose(pose(visible=False))
        self.assertEqual(result["confidence"], 0)
        self.assertEqual(result["review_priority"], 1)
        self.assertIsNone(result["suggested_phase"])


if __name__ == "__main__":
    unittest.main()
