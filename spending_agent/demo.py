"""Fictional sample data and per-visitor temporary SQLite storage."""

import os
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from .rules import today
from .storage import DEFAULT_DATABASE, TransactionStore

ENTRY_STATE_KEYS = ("pending_expense", "last_recorded_expense", "entry_error", "spending_message")


def sample_transactions(as_of):
    """A reproducible fictional dataset relative to the session's start date."""
    day = date.fromisoformat(as_of)
    monday = day - timedelta(days=day.weekday())
    rows = [
        (monday - timedelta(days=7), "22", "Dining", "Demo Noodle Corner", "Cash"),
        (monday - timedelta(days=7), "12", "Transport", "Demo City Ride", "WeChat Pay"),
        (monday - timedelta(days=6), "45", "Entertainment", "Demo Cinema", "Alipay"),
        (monday - timedelta(days=4), "80", "Shopping", "Demo Paper Shop", "Bank Card"),
        (monday - timedelta(days=2), "38", "Dining", "Demo Kitchen", "Alipay"),
        (monday, "35", "Dining", "Demo Lunch Cafe", "WeChat Pay"),
        (day - timedelta(days=1), "28", "Dining", "Demo Coffee House", "Alipay"),
        (day, "46", "Transport", "Demo City Ride", None),
        (day, "129", "Shopping", "Demo Clothing Store", "Bank Card"),
        (day, "60", "Entertainment", "Demo Cinema", "Alipay"),
    ]
    return [dict(amount=amount, category=category, merchant=merchant,
                 payment_method=payment, transaction_date=when.isoformat(),
                 notes="Fictional portfolio sample — not a real purchase")
            for when, amount, category, merchant, payment in rows]


class DemoSession:
    """One random temporary directory per session; never opens personal data.

    The object stays in that visitor's Streamlit session_state, not in a global
    cache. TemporaryDirectory cleans up when the object is released. An abrupt
    process exit may leave an orphan temp file, never reused by another session.
    """
    def __init__(self, as_of=None):
        self.as_of = as_of or today()
        self.directory = TemporaryDirectory(prefix="cash-crash-demo-")
        self.store = TransactionStore(Path(self.directory.name) / "demo.sqlite3")
        for record in sample_transactions(self.as_of):
            self.store.create_transaction(**record)

    def close(self):
        self.directory.cleanup()


def resolve_mode(forced=None):
    # Public entrypoint passes demo explicitly, ignoring server environment.
    mode = forced if forced is not None else os.environ.get("CASH_CRASH_MODE", "demo")
    if mode not in ("demo", "local"):
        raise ValueError("CASH_CRASH_MODE must be demo or local.")
    return mode


def session_store(state, mode, as_of):
    """Select a backend without ever considering SPENDING_DATABASE in demo mode."""
    identity = (mode, str(os.environ.get("SPENDING_DATABASE", DEFAULT_DATABASE)) if mode == "local" else "demo")
    if state.get("_cash_crash_identity") != identity:
        old = state.pop("_cash_crash_demo", None)
        if old is not None:
            old.close()
        for key in ENTRY_STATE_KEYS:
            state.pop(key, None)
        state["_cash_crash_identity"] = identity
    if mode == "local":
        return TransactionStore(identity[1])
    if mode != "demo":
        raise ValueError("Unknown mode.")
    if "_cash_crash_demo" not in state:
        state["_cash_crash_demo"] = DemoSession(as_of)
    return state["_cash_crash_demo"].store


def reset_demo(state):
    """Replace only this visitor's dataset and clear pending/saved UI messages."""
    old = state.get("_cash_crash_demo")
    if old is None:
        return
    replacement = DemoSession(old.as_of)
    state["_cash_crash_demo"] = replacement
    for key in ENTRY_STATE_KEYS:
        state.pop(key, None)
    old.close()
