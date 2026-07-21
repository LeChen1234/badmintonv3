import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.active_learning_service import evaluate_round, recommend_weights


CONFIG = {
    "minimum_rounds": 3,
    "stopping_patience": 2,
    "minimum_macro_f1_gain_per_hour": 0.01,
    "confidence_z": 1.96,
    "weight_update_rate": 0.3,
    "minimum_component_weight": 0.05,
    "initial_component_weights": {"motion": 0.4, "entropy": 0.25, "spectral": 0.2, "calculus": 0.15},
}


class ActiveLearningServiceTests(unittest.TestCase):
    def test_positive_ablation_gain_increases_component_weight(self):
        updated = recommend_weights(None, {"calculus": 1.0}, CONFIG)
        self.assertGreater(updated["calculus"], CONFIG["initial_component_weights"]["calculus"])
        self.assertAlmostEqual(sum(updated.values()), 1.0)

    @patch("app.services.active_learning_service.load_research_protocol", return_value={"active_learning": CONFIG})
    def test_stops_after_persistent_low_upper_gain(self, _):
        prior = [
            SimpleNamespace(metrics={"macro_f1_mean": 0.70, "macro_f1_std": 0}, recommended_weights=CONFIG["initial_component_weights"], marginal_utility={"upper_gain_per_hour": None}),
            SimpleNamespace(metrics={"macro_f1_mean": 0.701, "macro_f1_std": 0}, recommended_weights=CONFIG["initial_component_weights"], marginal_utility={"upper_gain_per_hour": 0.001}),
        ]
        utility, _, stop, decision = evaluate_round(
            prior, {"macro_f1_mean": 0.702, "macro_f1_std": 0}, 1.0, {}
        )
        self.assertLess(utility["upper_gain_per_hour"], 0.01)
        self.assertTrue(stop)
        self.assertTrue(decision["stop_recommended"])


if __name__ == "__main__":
    unittest.main()
