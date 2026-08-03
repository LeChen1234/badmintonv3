import unittest

from app.services.teacher_surrogate_service import _distribution, _entropy, _js_divergence, _learn_transition, _project


class TeacherSurrogateMathTests(unittest.TestCase):
    def setUp(self):
        self.classes = ["a", "b", "c"]

    def test_distribution_normalizes_and_rejects_empty(self):
        self.assertEqual(_distribution({}, self.classes), None)
        result = _distribution({"a": 2, "b": 1}, self.classes)
        self.assertAlmostEqual(sum(result.values()), 1.0)
        self.assertAlmostEqual(result["a"], 2 / 3)

    def test_js_is_zero_for_identical_and_bounded(self):
        value = {"a": 0.7, "b": 0.2, "c": 0.1}
        self.assertAlmostEqual(_js_divergence(value, value), 0.0)
        self.assertLessEqual(_js_divergence(value, {"a": 0, "b": 0, "c": 1}), 1.0)

    def test_entropy_separates_certain_and_uniform(self):
        self.assertLess(_entropy({"a": 1, "b": 0, "c": 0}), 0.01)
        self.assertAlmostEqual(_entropy({"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}), 1.0)

    def test_learned_transition_moves_distribution_toward_teacher(self):
        pairs = [
            ({"a": 0.9, "b": 0.1, "c": 0}, {"a": 0.1, "b": 0.8, "c": 0.1})
            for _ in range(20)
        ]
        matrix = _learn_transition(pairs, self.classes)
        estimate = _project(pairs[0][0], matrix, {"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}, calibrated=True)
        self.assertGreater(estimate["b"], estimate["a"])


if __name__ == "__main__":
    unittest.main()
