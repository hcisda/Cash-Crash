"""Parser examples, ambiguity checks, and record-command persistence."""

from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from spending_agent.parser import parse_transaction

ROOT = Path(__file__).resolve().parents[1]


class ParserTests(unittest.TestCase):
    def parse(self, message):
        return parse_transaction(message, reference_date=date(2026, 9, 17))

    def test_requested_examples(self):
        examples = [
            ("Lunch 35 WeChat", "35.00", "Dining", None, "WeChat Pay", "2026-09-17"),
            ("Starbucks 28 Alipay", "28.00", "Dining", "Starbucks", "Alipay", "2026-09-17"),
            ("Taxi 46", "46.00", "Transport", None, None, "2026-09-17"),
            ("Bought a coat for 699 yesterday", "699.00", "Shopping", None, None, "2026-09-16"),
        ]
        for message, amount, category, merchant, payment, day in examples:
            with self.subTest(message=message):
                self.assertEqual(self.parse(message), {
                    "amount": amount, "currency": "CNY", "category": category,
                    "merchant": merchant, "payment_method": payment,
                    "transaction_date": day, "notes": message,
                })

    def test_dates_and_shared_default(self):
        self.assertEqual(self.parse("Lunch 35 today")["transaction_date"], "2026-09-17")
        self.assertEqual(self.parse("Lunch 35 on 2026-08-01")["transaction_date"], "2026-08-01")
        self.assertEqual(parse_transaction("Taxi 46 yesterday", reference_date=date(2026, 1, 1))["transaction_date"], "2025-12-31")
        with patch("spending_agent.parser.today", return_value="2026-04-01"):
            self.assertEqual(parse_transaction("Taxi 46")["transaction_date"], "2026-04-01")

    def test_merchant_and_exact_amount(self):
        record = self.parse("Lunch at Corner Cafe for CNY35.50 using cash today")
        self.assertEqual(record["merchant"], "Corner Cafe")
        self.assertEqual(record["amount"], "35.50")
        self.assertEqual(record["category"], "Dining")
        self.assertEqual(self.parse("Something 20")["category"], "Other")
        self.assertIsNone(self.parse("Something 20")["merchant"])

    def test_payment_aliases_and_case(self):
        for alias, expected in (("wechat", "WeChat Pay"), ("WECHAT PAY", "WeChat Pay"),
                                ("alipay", "Alipay"), ("credit card", "Bank Card"),
                                ("Bank Card", "Bank Card"), ("cash", "Cash"),
                                ("other payment", "Other")):
            with self.subTest(alias=alias):
                self.assertEqual(self.parse(f"LUNCH 35 {alias}")["payment_method"], expected)

    def test_categories(self):
        for word, category in (("Rent", "Housing"), ("Electricity", "Utilities"),
                               ("Medicine", "Health"), ("Tuition", "Education"),
                               ("Hotel", "Travel"), ("Cinema", "Entertainment")):
            self.assertEqual(self.parse(f"{word} 50")["category"], category)

    def test_reject_ambiguous_or_invalid_messages(self):
        for message in ("", "Lunch", "Lunch 35 taxi 46", "Lunch 35 and taxi",
                        "Lunch 35 WeChat Alipay", "Lunch 35 today yesterday",
                        "Lunch -35", "Lunch 0", "Lunch 35.999", "Lunch 1,000",
                        "Lunch 35k", "Lunch $35", "Lunch 35 USD", "Refund 35",
                        "Lunch 35 last week", "Lunch 35 tomorrow", "Lunch 35 9/16",
                        "Lunch 35 on 2026-02-30", "Lunch 2e3", "Lunch 1.2.3"):
            with self.subTest(message=message), self.assertRaises(ValueError):
                self.parse(message)

    def test_record_command_persists_and_errors_do_not_save(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "record.sqlite3")

            def run(*args):
                return subprocess.run(
                    [sys.executable, "-m", "spending_agent", "--db", database, *args],
                    cwd=ROOT, capture_output=True, text=True,
                )

            recorded = run("record", "Lunch 35 WeChat")
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            self.assertIn("Saved transaction #", recorded.stdout)
            listed = run("list")  # New application process, same database.
            self.assertEqual(listed.returncode, 0, listed.stderr)
            records = json.loads(listed.stdout)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["amount"], "35.00")
            self.assertEqual(records[0]["payment_method"], "WeChat Pay")
            rejected = run("record", "Lunch 35 taxi 46")
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("exactly one numeric amount", rejected.stderr)
            self.assertNotIn("Saved transaction", rejected.stdout)
            self.assertEqual(json.loads(run("list").stdout), records)


if __name__ == "__main__":
    unittest.main()
