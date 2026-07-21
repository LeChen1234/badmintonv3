import unittest

from app.services.pose_service import _intersection_over_smaller, _nms, _normalized_pose_distance


def candidate(box, offset=0.0, confidence=0.9):
    points = [[20.0 + index * 2 + offset, 20.0 + index * 3 + offset] for index in range(17)]
    return {
        "bbox_px": box,
        "xy": points,
        "conf": [0.9] * 17,
        "detection_confidence": confidence,
        "source": "test",
    }


class PoseDedupTest(unittest.TestCase):
    def test_partial_and_full_detection_of_same_person_are_merged(self):
        full = candidate([10, 10, 90, 190], confidence=0.95)
        partial = candidate([20, 20, 80, 140], offset=1.0, confidence=0.82)

        self.assertGreater(_intersection_over_smaller(full["bbox_px"], partial["bbox_px"]), 0.9)
        self.assertLess(_normalized_pose_distance(full, partial), 0.02)
        self.assertEqual(_nms([full, partial]), [full])

    def test_overlapping_boxes_with_different_poses_are_kept(self):
        first = candidate([10, 10, 90, 190], confidence=0.95)
        second = candidate([20, 20, 80, 140], offset=60.0, confidence=0.85)

        self.assertEqual(len(_nms([first, second])), 2)

    def test_low_confidence_joints_do_not_create_false_match(self):
        first = candidate([10, 10, 90, 190])
        second = candidate([20, 20, 80, 140], offset=1.0)
        second["conf"] = [0.01] * 17

        self.assertEqual(_normalized_pose_distance(first, second), float("inf"))
        self.assertEqual(len(_nms([first, second])), 2)


if __name__ == "__main__":
    unittest.main()
