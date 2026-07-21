import unittest

from app.services.information_selection_service import diverse_indices, score_motion_sequence


class InformationSelectionTests(unittest.TestCase):
    def test_constant_sequence_has_no_motion_or_calculus_information(self):
        rows = score_motion_sequence([0.2] * 12)
        self.assertTrue(all(row["motion"] == 0 for row in rows))
        self.assertTrue(all(row["calculus"] == 0 for row in rows))
        self.assertTrue(all(row["entropy"] == 0 for row in rows))

    def test_impulse_is_ranked_above_stable_motion(self):
        rows = score_motion_sequence([0.1] * 6 + [1.0] + [0.1] * 6)
        self.assertGreater(rows[6]["score"], rows[2]["score"])
        self.assertGreater(rows[6]["calculus"], 0.5)

    def test_all_components_are_bounded_and_exposed(self):
        rows = score_motion_sequence([0.1, 0.2, 0.5, 0.15, 0.8, 0.1])
        for row in rows:
            for key in ("score", "motion", "entropy", "spectral", "calculus"):
                self.assertGreaterEqual(row[key], 0)
                self.assertLessEqual(row[key], 1)
            for key in ("velocity", "acceleration", "jerk"):
                self.assertIn(key, row)

    def test_diversity_suppresses_adjacent_duplicates(self):
        selected = diverse_indices([0.1, 0.9, 0.85, 0.8, 0.2, 0.95], 0.7, min_gap=2)
        self.assertEqual(selected, [1, 5])


if __name__ == "__main__":
    unittest.main()
