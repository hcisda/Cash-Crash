"""Session isolation, reset, public defaults and source-only packaging."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from streamlit.testing.v1 import AppTest

from spending_agent.demo import session_store, reset_demo, resolve_mode
from spending_agent.storage import TransactionStore
from tools.build_public_demo import build, PUBLIC_FILES

ROOT = Path(__file__).resolve().parents[1]


class DemoTests(unittest.TestCase):
    def test_isolation_and_reset(self):
        first, second = {}, {}
        a = session_store(first, "demo", "2026-09-17")
        b = session_store(second, "demo", "2026-09-17")
        self.addCleanup(lambda: first["_cash_crash_demo"].close())
        self.addCleanup(lambda: second["_cash_crash_demo"].close())
        original = [{k: v for k, v in row.items() if k not in ("created_at", "updated_at")}
                    for row in a.retrieve_transactions()]
        self.assertNotEqual(a.database_path, b.database_path)
        a.create_transaction(amount="987", category="Other", notes="Visitor A only")
        self.assertEqual(len(a.retrieve_transactions()), 11)
        self.assertEqual(len(b.retrieve_transactions()), 10)
        first["pending_expense"] = {"amount": "999"}
        reset_demo(first)
        restored = session_store(first, "demo", "2026-09-17")
        self.assertEqual([{k: v for k, v in row.items() if k not in ("created_at", "updated_at")}
                          for row in restored.retrieve_transactions()], original)
        self.assertNotIn("pending_expense", first)
        self.assertFalse(a.database_path.exists())
        self.assertEqual(len(b.retrieve_transactions()), 10)

    def test_demo_does_not_open_personal_database(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "personal.sqlite3"
            personal = TransactionStore(path)
            personal.create_transaction(amount="76543", category="Other", notes="PRIVATE_SENTINEL")
            before = path.read_bytes()
            state = {}
            with patch.dict(os.environ, {"SPENDING_DATABASE": str(path)}):
                demo = session_store(state, "demo", "2026-09-17")
                self.assertNotIn("PRIVATE_SENTINEL", str(demo.retrieve_transactions()))
                self.assertEqual(path.read_bytes(), before)
                state["_cash_crash_demo"].close()

    def test_public_entry_forces_demo_and_ui_isolates_visitors(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
            "CASH_CRASH_MODE": "local", "SPENDING_DATABASE": str(Path(folder) / "must-not-exist.sqlite3")
        }), patch("spending_agent.rules.today", return_value="2026-09-17"), patch(
            "spending_agent.parser.today", return_value="2026-09-17"
        ):
            a = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60).run()
            b = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60).run()
            self.addCleanup(lambda: a.session_state["_cash_crash_demo"].close())
            self.addCleanup(lambda: b.session_state["_cash_crash_demo"].close())
            self.assertEqual(len(a.exception), 0)
            self.assertEqual(a.title[0].value, "Cash Crash")
            self.assertTrue(any("Demo Mode" in notice.value for notice in a.info))
            before = [m.value for m in a.metric]
            a.text_input(key="spending_message").set_value("Lunch 35 WeChat")
            next(button for button in a.button if button.label == "Review expense").click().run()
            a.button(key="record_expense").click().run()
            self.assertEqual(len(a.exception), 0)
            self.assertEqual(len(a.dataframe[0].value), 11)
            self.assertNotEqual(a.metric[0].value, before[0])
            b.run()
            self.assertEqual(len(b.dataframe[0].value), 10)
            self.assertEqual([m.value for m in b.metric], before)
            a.button(key="reset_demo").click().run()
            self.assertEqual(len(a.exception), 0)
            self.assertEqual(len(a.dataframe[0].value), 10)
            self.assertEqual([m.value for m in a.metric], before)
            self.assertEqual(len(a.success), 0)
            self.assertFalse(Path(os.environ["SPENDING_DATABASE"]).exists())

    def test_safe_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_mode(), "demo")
        with patch.dict(os.environ, {"CASH_CRASH_MODE": "local"}):
            self.assertEqual(resolve_mode("demo"), "demo")
            self.assertEqual(resolve_mode(), "local")

    def test_public_archive_and_git_exclusions(self):
        with tempfile.TemporaryDirectory() as folder:
            archive_path = build(Path(folder) / "public.zip")
            with ZipFile(archive_path) as archive:
                self.assertEqual(set(archive.namelist()), set(PUBLIC_FILES))
                self.assertFalse(any(name.startswith(("data/", "sources/", ".venv/"))
                                     or name.endswith((".sqlite3", ".db", "secrets.toml", ".env"))
                                     for name in archive.namelist()))
            # Verify actual Git ignore behavior in a disposable repository.
            subprocess.run(["git", "init", "--quiet", folder], check=True, capture_output=True)
            (Path(folder) / ".gitignore").write_bytes((ROOT / ".gitignore").read_bytes())
            for name in ("data/spending.sqlite3", ".streamlit/secrets.toml", ".env", "sources/private.txt"):
                result = subprocess.run(["git", "-C", folder, "check-ignore", name], capture_output=True)
                self.assertEqual(result.returncode, 0, name)


if __name__ == "__main__":
    unittest.main()
