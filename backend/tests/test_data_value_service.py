import unittest

from app.services.data_value_service import _cross_entropy, _entropy, _loss_to_unit


class DataValueMathTests(unittest.TestCase):
    def test_cross_entropy_uses_labeled_probability(self):
        easy = _cross_entropy({"a": 0.9, "b": 0.1}, "a")
        hard = _cross_entropy({"a": 0.2, "b": 0.8}, "a")
        self.assertLess(easy, hard)
        self.assertIsNone(_cross_entropy({"a": 1.0}, "missing"))

    def test_entropy_is_normalized(self):
        self.assertAlmostEqual(_entropy({"a": 0.5, "b": 0.5}), 1.0)
        self.assertLess(_entropy({"a": 0.99, "b": 0.01}), 0.1)

    def test_bounded_loss_preserves_order(self):
        low = _loss_to_unit(0.2)
        high = _loss_to_unit(3.0)
        self.assertGreater(high, low)
        self.assertLess(high, 1.0)


if __name__ == "__main__":
    unittest.main()
