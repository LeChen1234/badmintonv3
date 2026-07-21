import importlib.util
import unittest
from pathlib import Path

import numpy as np

SPEC = importlib.util.spec_from_file_location("micro_probe", Path(__file__).parents[2] / "scripts" / "micro_train_data_probe.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class MicroTrainProbeTests(unittest.TestCase):
    @staticmethod
    def pose(label, group, offset=0):
        return {
            "action_type": label,
            "match_uuid": group,
            "keypoints": [
                {"name": name, "x": 10 + i + offset, "y": 20 + (i % 5), "visibility": 2}
                for i, name in enumerate(probe.KEYPOINTS)
            ],
        }

    def test_linear_probe_learns_separable_signal(self):
        rng = np.random.default_rng(3)
        x = np.r_[rng.normal(-1, .15, (30, 6)), rng.normal(1, .15, (30, 6))]
        y = np.r_[np.zeros(30, dtype=int), np.ones(30, dtype=int)]
        w, b, mean, std = probe.fit_probe(x, y, 2, seed=0, epochs=150)
        result = probe.metrics(probe.softmax(((x - mean) / std) @ w + b), y)
        self.assertGreater(result["macro_f1"], .95)

    def test_pose_feature_is_translation_and_scale_invariant(self):
        def record(offset, scale):
            return {"keypoints": [
                {"name": name, "x": offset + i * scale, "y": offset + (i % 5) * scale, "visibility": 2}
                for i, name in enumerate(probe.KEYPOINTS)
            ]}
        a, b = probe.pose_feature(record(10, 1)), probe.pose_feature(record(40, 3))
        np.testing.assert_allclose(a, b, atol=1e-8)

    def test_equal_budget_is_class_stratified(self):
        baseline = [self.pose("smash", "b", i) for i in range(4)] + [self.pose("clear", "b", i) for i in range(2)]
        curated = [self.pose("smash", "c", i) for i in range(2)] + [self.pose("clear", "c", i) for i in range(5)]
        left, right, budget = probe.equalize_training_sets(baseline, curated, "action_type")
        self.assertEqual(budget, {"clear": 2, "smash": 2})
        self.assertEqual(len(left), len(right))

    def test_group_leakage_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "leakage"):
            probe.assert_group_isolation([self.pose("smash", "same")], [self.pose("clear", "same")], "curated")

    def test_paired_bootstrap_detects_strictly_better_predictions(self):
        truth = np.asarray([0, 1] * 20)
        baseline = np.full((40, 2), 0.5)
        curated = np.eye(2)[truth] * 0.9 + 0.05
        result = probe.paired_bootstrap(baseline, curated, truth, iterations=200, seed=1)
        self.assertGreater(result["macro_f1"]["probability_curated_better"], 0.95)
        self.assertGreater(result["macro_f1"]["ci95"][0], 0)


if __name__ == "__main__":
    unittest.main()
