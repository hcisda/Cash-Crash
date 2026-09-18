"""Exercise real parser/storage through Streamlit, in disposable databases."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from spending_agent.storage import TransactionStore

ROOT = Path(__file__).resolve().parents[1]


class EntryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = TransactionStore(Path(self.temp.name) / "entry.sqlite3")
        for context in (
            patch.dict(os.environ, {"SPENDING_DATABASE": str(self.store.database_path), "CASH_CRASH_MODE": "local"}),
            patch("spending_agent.rules.today", return_value="2026-09-17"),
            patch("spending_agent.parser.today", return_value="2026-09-17"),
        ):
            context.start()
            self.addCleanup(context.stop)
        self.app = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=30).run()

    def review(self, message):
        self.app.text_input(key="spending_message").set_value(message)
        next(button for button in self.app.button if button.label == "Review expense").click().run()

    def test_preview_save_refresh_and_no_duplicate_reruns(self):
        self.review("Lunch 35 WeChat")
        self.assertEqual(self.store.retrieve_transactions(), [])
        self.app.button(key="record_expense").click().run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertIn("Recorded ¥35.00 · Dining · WeChat Pay · Sep 17", self.app.success[0].value)
        self.assertEqual([m.value for m in self.app.metric[:3]], ["¥35.00"] * 3)
        self.assertEqual(len(self.app.get("arrow_vega_lite_chart")), 3)
        self.assertEqual(len(self.app.dataframe[0].value), 1)
        saved = self.store.retrieve_transactions()[0]
        self.assertIsNone(saved["merchant"])
        self.assertEqual(saved["payment_method"], "WeChat Pay")
        self.assertFalse(any(b.label == "Record expense" for b in self.app.button))
        self.app.run()
        self.app.selectbox[0].select(90).run()
        next(b for b in self.app.button if b.label == "Refresh data").click().run()
        self.assertEqual(len(self.store.retrieve_transactions()), 1)
        self.assertEqual(len(self.app.exception), 0)

    def test_missing_fields_and_yesterday(self):
        self.review("Bought a coat for 699 yesterday")
        self.app.button(key="record_expense").click().run()
        saved = self.store.retrieve_transactions()[0]
        self.assertEqual(saved["transaction_date"], "2026-09-16")
        self.assertIsNone(saved["merchant"])
        self.assertIsNone(saved["payment_method"])
        self.assertEqual(self.app.metric[0].value, "¥0.00")
        self.assertEqual(self.app.metric[1].value, "¥699.00")

    def test_invalid_message_clears_old_draft(self):
        self.review("Taxi 46")
        self.review("Lunch 35 taxi 46")
        self.assertTrue(self.app.error)
        self.assertFalse(any(b.label == "Record expense" for b in self.app.button))
        self.assertEqual(self.store.retrieve_transactions(), [])

    def test_discard_and_intentional_repeat(self):
        self.review("Taxi 46")
        self.app.button(key="discard_expense").click().run()
        self.assertEqual(self.store.retrieve_transactions(), [])
        for _ in range(2):
            self.review("Taxi 46")
            self.app.button(key="record_expense").click().run()
        self.assertEqual(len(self.store.retrieve_transactions()), 2)

    def test_failed_save_keeps_preview_for_retry(self):
        self.review("Starbucks 28 Alipay")
        with patch.object(TransactionStore, "create_transaction", side_effect=sqlite3.OperationalError("database is locked")):
            self.app.button(key="record_expense").click().run()
        self.assertTrue(self.app.error)
        self.assertEqual(self.store.retrieve_transactions(), [])
        self.app.button(key="record_expense").click().run()
        self.assertEqual(len(self.store.retrieve_transactions()), 1)
        self.assertEqual(self.store.retrieve_transactions()[0]["merchant"], "Starbucks")


if __name__ == "__main__":
    unittest.main()
