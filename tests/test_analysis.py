import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_portfolio import monthly_risk


class PortfolioRiskTests(unittest.TestCase):
    def test_identical_holding_and_benchmark_have_unit_beta(self):
        months = pd.date_range("2023-10-31", periods=37, freq="ME")
        returns = np.array([0.01 + (i % 5 - 2) * 0.006 for i in range(36)])
        prices = np.concatenate(([100.0], 100.0 * np.cumprod(1 + returns)))
        history = pd.DataFrame({"ALPH": prices, "^GSPC": prices}, index=months)
        treasury = pd.Series(0.04, index=months)
        result = monthly_risk(history, treasury, {"ALPH": 1.0}, "2026-11-19")
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["observations"], 36)
        self.assertAlmostEqual(result["beta"], 1.0)
        self.assertTrue(np.isfinite(result["sharpe"]))


if __name__ == "__main__":
    unittest.main()
