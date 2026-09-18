"""Known SQLite fixtures with independently calculated expected totals."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from spending_agent.analytics import summarize, spending_by, compare_periods, period_ranges
from spending_agent.storage import TransactionStore

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = [
    ("2026-08-01", "80", "Dining", "Cash"),
    ("2026-08-17", "20", "Transport", None),
    ("2026-08-18", "999", "Other", "Cash"),
    ("2026-09-01", "100", "Housing", "Bank Card"),
    ("2026-09-07", "20", "Dining", "Cash"),
    ("2026-09-10", "30", "Transport", None),
    ("2026-09-10", "500", "Shopping", "Alipay"),
    ("2026-09-14", "35", "Dining", "WeChat Pay"),
    ("2026-09-15", "28", "Dining", "Alipay"),
    ("2026-09-17", "46", "Transport", None),
    ("2026-09-17", "699", "Shopping", "Alipay"),
    ("2026-09-18", "999", "Other", "Cash"),
]


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "analytics.sqlite3"
        self.store = TransactionStore(self.path)
        for day, amount, category, payment in SAMPLES:
            self.store.create_transaction(amount=amount, category=category,
                                          payment_method=payment, transaction_date=day)
        self.records = self.store.retrieve_transactions()

    def test_totals_match_manual_arithmetic(self):
        # Today: 46 + 699 = 745; week: 35 + 28 + 46 + 699 = 808.
        # Month: 100 + 20 + 30 + 500 + 35 + 28 + 46 + 699 = 1458.
        for period, total, count in (("today", "745.00", 2), ("week", "808.00", 4),
                                     ("month", "1458.00", 8)):
            result = summarize(self.records, period, "2026-09-17")
            self.assertEqual(result["total"], total)
            self.assertEqual(result["transaction_count"], count)
            self.assertEqual(result["highest_spending_categories"], ["Shopping"])

    def test_breakdowns_reconcile(self):
        category = spending_by(self.records, "category", "month", "2026-09-17")
        self.assertEqual({r["category"]: r["amount"] for r in category["groups"]},
                         {"Dining": "83.00", "Transport": "76.00", "Shopping": "1199.00", "Housing": "100.00"})
        payment = spending_by(self.records, "payment_method", "month", "2026-09-17")
        self.assertEqual({r["payment_method"]: r["amount"] for r in payment["groups"]},
                         {"Cash": "20.00", "Bank Card": "100.00", "Alipay": "1227.00",
                          "WeChat Pay": "35.00", "Unknown": "76.00"})
        self.assertEqual(category["total"], payment["total"])

    def test_week_variance(self):
        result = compare_periods(self.records, "week", "2026-09-17")
        self.assertEqual(result["current_range"], {"start": "2026-09-14", "end": "2026-09-17", "days": 4})
        self.assertEqual(result["previous_range"], {"start": "2026-09-07", "end": "2026-09-10", "days": 4})
        self.assertEqual(result["previous_total"], "550.00")
        self.assertEqual(result["change_amount"], "258.00")
        self.assertEqual(result["change_percent"], "46.91")
        self.assertEqual(result["largest_increase_categories"], ["Shopping"])
        self.assertEqual(result["largest_increase_amount"], "199.00")
        self.assertEqual([row["change_amount"] for row in result["categories"]], ["199.00", "43.00", "16.00"])

    def test_month_variance(self):
        result = compare_periods(self.records, "month", "2026-09-17")
        self.assertEqual(result["previous_total"], "100.00")  # August 18 is excluded.
        self.assertEqual(result["current_total"], "1458.00")  # September 18 is excluded.
        self.assertEqual(result["change_amount"], "1358.00")
        self.assertEqual(result["change_percent"], "1358.00")
        shopping = next(row for row in result["categories"] if row["category"] == "Shopping")
        self.assertIsNone(shopping["change_percent"])

    def test_empty_periods_and_zero_baselines(self):
        self.assertEqual(summarize([], "today", "2026-09-17")["total"], "0.00")
        self.assertEqual(spending_by([], as_of="2026-09-17")["groups"], [])
        result = compare_periods([], as_of="2026-09-17")
        self.assertIsNone(result["change_percent"])
        self.assertEqual(result["largest_increase_categories"], [])
        self.assertEqual(result["highest_spending_categories"], [])
        current_only = [r for r in self.records if r["transaction_date"] == "2026-09-17"]
        self.assertIsNone(compare_periods(current_only, as_of="2026-09-17")["change_percent"])

    def test_declines_and_no_increase(self):
        previous_only = [r for r in self.records if r["transaction_date"] == "2026-09-10"]
        result = compare_periods(previous_only, as_of="2026-09-17")
        self.assertEqual(result["change_amount"], "-530.00")
        self.assertEqual(result["change_percent"], "-100.00")
        self.assertEqual(result["largest_increase_categories"], [])
        self.assertEqual(result["largest_increase_amount"], "0.00")

    def test_exact_cents_and_ties(self):
        records = [dict(amount=amount, category=category, currency="CNY",
                        payment_method=None, transaction_date="2026-09-17")
                   for amount, category in (("0.10", "Dining"), ("0.20", "Dining"), ("0.30", "Transport"))]
        result = summarize(records, "today", "2026-09-17")
        self.assertEqual(result["total"], "0.60")
        self.assertEqual(result["highest_spending_categories"], ["Dining", "Transport"])
        self.assertEqual(compare_periods(records, as_of="2026-09-17")["largest_increase_categories"], ["Dining", "Transport"])

    def test_calendar_boundaries_and_default_date(self):
        for as_of, expected_end in (("2026-03-31", "2026-02-28"), ("2024-03-31", "2024-02-29"),
                                    ("2026-01-01", "2025-12-01")):
            self.assertEqual(period_ranges("month", as_of)[3].isoformat(), expected_end)
        self.assertFalse(compare_periods([], "month", "2026-03-31")["equal_day_counts"])
        self.assertEqual(period_ranges("week", "2026-09-14")[0].isoformat(), "2026-09-14")
        self.assertEqual(period_ranges("week", "2026-09-20")[0].isoformat(), "2026-09-14")
        with patch("spending_agent.analytics.today", return_value="2026-09-17"):
            self.assertEqual(summarize(self.records, "today")["total"], "745.00")

    def test_invalid_options(self):
        with self.assertRaises(ValueError):
            summarize(self.records, "year")
        with self.assertRaises(ValueError):
            summarize(self.records, as_of="2026-02-30")
        with self.assertRaises(ValueError):
            spending_by(self.records, "merchant")
        with self.assertRaises(ValueError):
            compare_periods(self.records, "today")

    def test_cli_reads_database_without_changing_records(self):
        for command in ("summary", "categories", "payments", "compare"):
            result = subprocess.run(
                [sys.executable, "-m", "spending_agent", "--db", str(self.path), command,
                 "--period", "week", "--as-of", "2026-09-17"],
                cwd=ROOT, capture_output=True, text=True, check=True,
            )
            output = json.loads(result.stdout)
            self.assertEqual(output["current_total" if command == "compare" else "total"], "808.00")
        self.assertEqual(self.store.retrieve_transactions(), self.records)


if __name__ == "__main__":
    unittest.main()
