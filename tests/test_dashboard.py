"""Streamlit UI checks against temporary databases; no personal data writes."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from spending_agent.analytics import daily_spending
from spending_agent.storage import TransactionStore

ROOT = Path(__file__).resolve().parents[1]


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = TransactionStore(Path(self.temp.name) / "dashboard.sqlite3")
        environment = patch.dict(os.environ, {"SPENDING_DATABASE": str(self.store.database_path), "CASH_CRASH_MODE": "local"})
        environment.start()
        self.addCleanup(environment.stop)
        clock = patch("spending_agent.rules.today", return_value="2026-09-17")
        clock.start()
        self.addCleanup(clock.stop)

    def app(self):
        return AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=30).run()

    def add(self, amount, category, day, payment=None):
        self.store.create_transaction(amount=amount, category=category, transaction_date=day, payment_method=payment)

    def test_empty_dashboard(self):
        app = self.app()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([metric.value for metric in app.metric], ["¥0.00", "¥0.00", "¥0.00", "N/A"])
        self.assertTrue(any("No transactions yet" in item.value for item in app.info))
        self.assertEqual(len(app.get("arrow_vega_lite_chart")), 1)

    def test_populated_dashboard_and_refresh(self):
        for amount, category, day, payment in (
            ("20", "Dining", "2026-09-07", "Cash"),
            ("30", "Transport", "2026-09-10", None),
            ("500", "Shopping", "2026-09-10", "Alipay"),
            ("35", "Dining", "2026-09-14", "WeChat Pay"),
            ("28", "Dining", "2026-09-15", "Alipay"),
            ("46", "Transport", "2026-09-17", None),
            ("699", "Shopping", "2026-09-17", "Alipay"),
        ):
            self.add(amount, category, day, payment)
        before = self.store.retrieve_transactions()
        app = self.app()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([metric.value for metric in app.metric], ["¥745.00", "¥808.00", "¥1,358.00", "+46.91%"])
        self.assertEqual(len(app.get("arrow_vega_lite_chart")), 3)
        self.assertEqual(len(app.dataframe[0].value), 7)
        text = " ".join(item.value for item in app.markdown)
        self.assertIn("Shopping · ¥1,199.00", text)
        self.assertIn("Shopping · +¥199.00", text)
        self.assertEqual(self.store.retrieve_transactions(), before)
        app.selectbox[0].select(90).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("last 90 days" in item.value for item in app.subheader))
        self.add("1", "Other", "2026-09-17")
        app.button[0].click().run()
        self.assertEqual(app.metric[0].value, "¥746.00")

    def test_zero_baseline_and_future_records(self):
        self.add("35", "Dining", "2026-09-17")
        self.add("999", "Other", "2026-09-18")
        app = self.app()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.metric[0].value, "¥35.00")
        self.assertEqual(app.metric[3].value, "N/A")
        self.assertEqual(len(app.dataframe[0].value), 2)

    def test_trend_exact_cents_zero_days_and_boundaries(self):
        self.add("0.10", "Dining", "2026-09-16")
        self.add("0.20", "Dining", "2026-09-16")
        self.add("99", "Dining", "2026-09-14")
        self.add("99", "Dining", "2026-09-18")
        trend = daily_spending(self.store.retrieve_transactions(), 3, "2026-09-17")
        self.assertEqual(trend["total"], "0.30")
        self.assertEqual(trend["days"], [
            {"date": "2026-09-15", "amount": "0.00"},
            {"date": "2026-09-16", "amount": "0.30"},
            {"date": "2026-09-17", "amount": "0.00"},
        ])
        self.assertEqual(len(daily_spending([], 90, "2026-09-17")["days"]), 90)
        for invalid in (0, -1, 367, 1.5, True):
            with self.assertRaises(ValueError):
                daily_spending([], invalid)


if __name__ == "__main__":
    unittest.main()
