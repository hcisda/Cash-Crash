"""SQLite transaction storage, using a fresh connection for each operation."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .rules import CATEGORIES, PAYMENT_METHODS, EDITABLE_FIELDS, validate_transaction

DEFAULT_DATABASE = Path(__file__).resolve().parent.parent / "data" / "spending.sqlite3"


def _timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _record(row):
    if row is None:
        return None
    record = dict(row)
    fen = record.pop("amount_minor")
    # Return an exact decimal string instead of a floating-point approximation.
    record["amount"] = f"{fen // 100}.{fen % 100:02d}"
    return record


class TransactionStore:
    def __init__(self, database_path=DEFAULT_DATABASE):
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self):
        # These lists are application constants, never user-provided SQL.
        categories = ", ".join(f"'{value}'" for value in CATEGORIES)
        payments = ", ".join(f"'{value}'" for value in PAYMENT_METHODS)
        with self._connection() as connection:
            connection.execute(f"""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount_minor INTEGER NOT NULL
                        CHECK (typeof(amount_minor) = 'integer' AND amount_minor > 0),
                    currency TEXT NOT NULL DEFAULT 'CNY' CHECK (currency = 'CNY'),
                    category TEXT NOT NULL CHECK (category IN ({categories})),
                    merchant TEXT,
                    payment_method TEXT CHECK (payment_method IN ({payments})),
                    transaction_date TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def create_transaction(self, *, amount, category, currency="CNY", merchant=None,
                           payment_method=None, transaction_date=None, notes=None):
        values = validate_transaction(dict(
            amount=amount, category=category, currency=currency, merchant=merchant,
            payment_method=payment_method, transaction_date=transaction_date, notes=notes,
        ))
        now = _timestamp()
        values.update(created_at=now, updated_at=now)
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self._connection() as connection:
            cursor = connection.execute(
                f"INSERT INTO transactions ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
            return _record(connection.execute(
                "SELECT * FROM transactions WHERE id = ?", (cursor.lastrowid,),
            ).fetchone())

    def get_transaction(self, transaction_id):
        with self._connection() as connection:
            return _record(connection.execute(
                "SELECT * FROM transactions WHERE id = ?", (transaction_id,),
            ).fetchone())

    def retrieve_transactions(self):
        with self._connection() as connection:
            return [_record(row) for row in connection.execute(
                "SELECT * FROM transactions ORDER BY transaction_date DESC, id DESC"
            ).fetchall()]

    def update_transaction(self, transaction_id, **changes):
        unknown = set(changes) - EDITABLE_FIELDS
        if unknown:
            raise ValueError(f"Cannot update fields: {', '.join(sorted(unknown))}")
        with self._connection() as connection:
            # Read and write under one transaction to avoid losing concurrent edits.
            connection.execute("BEGIN IMMEDIATE")
            existing = _record(connection.execute(
                "SELECT * FROM transactions WHERE id = ?", (transaction_id,),
            ).fetchone())
            if existing is None:
                raise KeyError(f"Transaction {transaction_id} not found.")
            if not changes:
                return existing
            values = {key: existing[key] for key in EDITABLE_FIELDS}
            values.update(changes)
            normalized = validate_transaction(values)
            normalized["updated_at"] = _timestamp()
            assignments = ", ".join(f"{key} = ?" for key in normalized)
            connection.execute(
                f"UPDATE transactions SET {assignments} WHERE id = ?",
                (*normalized.values(), transaction_id),
            )
            return _record(connection.execute(
                "SELECT * FROM transactions WHERE id = ?", (transaction_id,),
            ).fetchone())

    def delete_transaction(self, transaction_id):
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM transactions WHERE id = ?", (transaction_id,),
            )
            return cursor.rowcount == 1

