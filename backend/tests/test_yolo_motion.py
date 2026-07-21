import unittest

from app.services.yolo_preprocess_service import (
    _match_people,
    _motion_score_between,
    _percentile,
)


def person(cx: float, cy: float = 100.0, scale: float = 1.0):
    points = [[0.0, 0.0] for _ in range(17)]
    template = [
        (-20, -40), (20, -40), (-30, -10), (30, -10), (-35, 20), (35, 20),
        (-15, 20), (15, 20), (-15, 60), (15, 60), (-15, 100), (15, 100),
    ]
    for idx, (x, y) in zip(range(5, 17), template):
        points[idx] = [cx + x * scale, cy + y * scale]
    return points


class MotionScoringTests(unittest.TestCase):
    def test_score_is_scale_invariant(self):
        small = _motion_score_between(person(100, scale=1), person(110, scale=1))[0] / 12
        large = _motion_score_between(person(200, scale=2), person(220, scale=2))[0] / 12
        self.assertAlmostEqual(small, large, places=7)

    def test_matching_survives_left_right_order_change(self):
        previous = [person(100), person(300)]
        current = [person(290), person(110)]  # detector order is deliberately reversed
        pairs = _match_people(previous, current)
        self.assertEqual(len(pairs), 2)
        motions = [_motion_score_between(a, b)[0] / 12 for a, b in pairs]
        self.assertTrue(all(score < 0.1 for score in motions))

    def test_percentile_interpolates_and_clamps(self):
        self.assertEqual(_percentile([0, 10, 20, 30], 50), 15)
        self.assertEqual(_percentile([1, 2], -1), 1)
        self.assertEqual(_percentile([1, 2], 101), 2)


if __name__ == "__main__":
    unittest.main()
