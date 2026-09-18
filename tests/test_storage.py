"""Run with: python -m unittest discover -s tests -v"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from spending_agent.rules import CATEGORIES, PAYMENT_METHODS, today
from spending_agent.storage import TransactionStore

ROOT = Path(__file__).resolve().parents[1]


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "test.sqlite3"
        self.store = TransactionStore(self.path)

    def test_create_defaults_and_exact_money(self):
        record = self.store.create_transaction(amount="35.10", category="Dining")
        self.assertEqual(record["amount"], "35.10")
        self.assertEqual(record["currency"], "CNY")
        self.assertEqual(record["transaction_date"], today())
        self.assertIsNone(record["merchant"])
        self.assertIsNone(record["payment_method"])
        self.assertEqual(record["created_at"], record["updated_at"])
        self.assertEqual(self.store.get_transaction(record["id"]), record)

    def test_update_clear_and_delete(self):
        original = self.store.create_transaction(
            amount="699", category="Shopping", merchant="Store", payment_method="Alipay",
            transaction_date="2026-09-16", notes="Coat",
        )
        updated = self.store.update_transaction(original["id"], amount="599.99", merchant=None)
        self.assertEqual(updated["amount"], "599.99")
        self.assertIsNone(updated["merchant"])
        self.assertEqual(updated["notes"], "Coat")
        self.assertEqual(updated["created_at"], original["created_at"])
        self.assertGreaterEqual(updated["updated_at"], original["updated_at"])
        self.assertTrue(self.store.delete_transaction(original["id"]))
        self.assertIsNone(self.store.get_transaction(original["id"]))
        self.assertFalse(self.store.delete_transaction(original["id"]))
        with self.assertRaises(KeyError):
            self.store.update_transaction(original["id"], amount="1")

    def test_invalid_records_are_not_saved(self):
        for change in (
            {"amount": "0"}, {"amount": "-1"}, {"amount": "abc"},
            {"amount": "NaN"}, {"amount": "Infinity"}, {"amount": "1.001"},
            {"amount": "92233720368547758.08"}, {"category": "Food"},
            {"payment_method": "Unknown"}, {"currency": "USD"},
            {"transaction_date": "2026-02-30"}, {"transaction_date": "20260917"},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.store.create_transaction(**({"amount": "35", "category": "Dining"} | change))
        self.assertEqual(self.store.retrieve_transactions(), [])

    def test_invalid_update_preserves_saved_data(self):
        record = self.store.create_transaction(amount="35", category="Dining")
        for change in ({"amount": "-1"}, {"id": 2}, {"created_at": "yesterday"}):
            with self.assertRaises(ValueError):
                self.store.update_transaction(record["id"], **change)
        self.assertEqual(self.store.get_transaction(record["id"]), record)

    def test_all_categories_and_payment_methods(self):
        for category in CATEGORIES:
            for payment in PAYMENT_METHODS:
                self.store.create_transaction(amount="1", category=category, payment_method=payment)
        self.assertEqual(len(self.store.retrieve_transactions()), len(CATEGORIES) * len(PAYMENT_METHODS))

    def test_sort_and_reopen(self):
        older = self.store.create_transaction(amount="1", category="Other", transaction_date="2026-01-01")
        newer = self.store.create_transaction(amount="2", category="Other", transaction_date="2026-02-01")
        reopened = TransactionStore(self.path)
        self.assertEqual([r["id"] for r in reopened.retrieve_transactions()], [newer["id"], older["id"]])

    def test_persistence_across_separate_application_processes(self):
        def run(*arguments):
            result = subprocess.run(
                [sys.executable, "-m", "spending_agent", "--db", str(self.path), *arguments],
                cwd=ROOT, capture_output=True, text=True, check=True,
            )
            return json.loads(result.stdout)

        saved = run("add", "--amount", "35", "--category", "Dining", "--payment-method", "WeChat Pay")
        # The add process has exited. A new interpreter reads the same file.
        self.assertEqual(run("get", str(saved["id"])), saved)
        self.assertEqual(run("list"), [saved])
        changed = run("update", str(saved["id"]), "--amount", "36")
        self.assertEqual(run("get", str(saved["id"])), changed)
        run("delete", str(saved["id"]))
        self.assertEqual(run("list"), [])


if __name__ == "__main__":
    unittest.main()
