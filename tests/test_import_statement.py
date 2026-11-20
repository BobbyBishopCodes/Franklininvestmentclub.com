import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from import_statement import parse_statement_text, prepare


STATEMENT = """FRANKLIN INVESTMENT CLUB
Statement as of 11/30/2026
100 Alpha Company (ALPH) $5.00 $500.00 $10.00 $1,000.00 66.67% $9.00 11.11% - $20
50 Beta Company (BETA) $4.00 $200.00 $10.00 $500.00 33.33% $9.00 11.11% - $5
Total Stock Value # of Positions = 2 $700.00 $1,500.00 100%
Cash & Credit Balance $10.00 0%
Total Club Portfolio Value $1,510.00 100%
"""


class StatementImportTests(unittest.TestCase):
    def test_reconciled_statement(self):
        result = parse_statement_text(STATEMENT)
        self.assertEqual(result["as_of"], "2026-11-30")
        self.assertEqual(len(result["positions"]), 2)
        self.assertEqual(str(result["total"]), "1510.00")
        rows = prepare(result, {"ALPH": "Technology", "BETA": "Industrials"}, [])
        self.assertEqual([row["total_cost"] for row in rows], ["500.00", "200.00"])
        self.assertEqual([row["annual_income"] for row in rows], ["20.00", "5.00"])

    def test_rejects_position_value_mismatch(self):
        altered = STATEMENT.replace("$1,000.00 66.67%", "$1,001.00 66.67%")
        with self.assertRaisesRegex(ValueError, "Shares × price"):
            parse_statement_text(altered)

    def test_rejects_missing_position(self):
        altered = "\n".join(line for line in STATEMENT.splitlines() if "Beta Company" not in line)
        with self.assertRaisesRegex(ValueError, "statement prints 2"):
            parse_statement_text(altered)

    def test_rejects_incorrect_portfolio_total(self):
        altered = STATEMENT.replace("$1,510.00", "$1,520.00")
        with self.assertRaisesRegex(ValueError, "Stock total plus cash"):
            parse_statement_text(altered)


if __name__ == "__main__":
    unittest.main()
