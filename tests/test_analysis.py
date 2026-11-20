import sys
import unittest
import math
import statistics
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_portfolio import monthly_risk, weekly_estimate


class PortfolioRiskTests(unittest.TestCase):
    def test_weekly_estimate_independent_reference(self):
        dates = pd.date_range(end='2026-10-30', periods=53, freq='W-FRI')
        returns = np.tile([-.01, .02, .005, -.003], 13)
        prices = np.r_[100, 100 * np.cumprod(1 + returns)]
        history = pd.DataFrame({'ALPH': prices}, index=dates)
        result = weekly_estimate(history, {'ALPH': .9}, '2026-10-31')
        rf = 1.0416 ** (1 / 52) - 1
        expected = [.9 * float(r) - rf for r in returns]
        self.assertAlmostEqual(result['sharpe'], math.sqrt(52) * statistics.mean(expected) / statistics.stdev(expected), places=12)
        self.assertAlmostEqual(result['compounded_annual_return'], math.prod(1 + .9 * float(r) for r in returns) - 1)
        self.assertEqual(result['observations'], 52)
        self.assertEqual(weekly_estimate(history.iloc[:-1], {'ALPH': 1}, '2026-10-31')['status'], 'unavailable')

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
        audited = result['monthly_audit']
        excess = [row['excess_return'] for row in audited]
        independent = math.sqrt(12) * statistics.mean(excess) / statistics.stdev(excess)
        self.assertAlmostEqual(result['sharpe'], independent, places=12)
        self.assertAlmostEqual(audited[0]['risk_free_return'], .04 * 30 / 365)

    def test_known_returns_cash_and_missing_history(self):
        months = pd.date_range('2023-10-31', periods=37, freq='ME')
        returns = np.tile([-.02, .01, .04], 12)
        values = np.r_[100, 100 * np.cumprod(1 + returns)]
        history = pd.DataFrame({'ALPH': values, '^GSPC': values}, index=months)
        result = monthly_risk(history, pd.Series(0., index=months), {'ALPH': .8}, '2026-11-19')
        expected = [.8 * float(r) for r in returns]
        self.assertAlmostEqual(result['sharpe'], math.sqrt(12) * statistics.mean(expected) / statistics.stdev(expected))
        self.assertAlmostEqual(result['beta'], .8)
        self.assertAlmostEqual(result['cash_weight'], .2)
        missing = monthly_risk(history.iloc[:-1], pd.Series(0., index=months), {'ALPH': 1.}, '2026-11-19')
        self.assertEqual(missing['status'], 'unavailable')


if __name__ == "__main__":
    unittest.main()
