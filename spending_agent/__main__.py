"""Small command-line interface for manually exercising the storage layer."""

import argparse
import json
import sqlite3

from .rules import CATEGORIES, PAYMENT_METHODS
from .storage import DEFAULT_DATABASE, TransactionStore
from .parser import parse_transaction
from .analytics import summarize, spending_by, compare_periods


def main():
    parser = argparse.ArgumentParser(description="Personal spending transaction storage")
    parser.add_argument("--db", default=str(DEFAULT_DATABASE), help="SQLite database file")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create the database if needed")
    commands.add_parser("record", help="Parse and save one simple spending sentence").add_argument("message")
    for action in ("summary", "categories", "payments", "compare"):
        command = commands.add_parser(action, help=f"Show spending {action}")
        command.add_argument("--period", choices=["week", "month"] if action == "compare"
                             else ["today", "week", "month"], default="month")
        command.add_argument("--as-of", help="Reference date YYYY-MM-DD; defaults to today in Shanghai")
    for action in ("add", "update"):
        command = commands.add_parser(action)
        if action == "update":
            command.add_argument("id", type=int)
        command.add_argument("--amount", required=action == "add")
        command.add_argument("--category", choices=CATEGORIES, required=action == "add")
        command.add_argument("--currency", choices=["CNY"])
        command.add_argument("--merchant")
        command.add_argument("--payment-method", choices=PAYMENT_METHODS)
        command.add_argument("--date", dest="transaction_date")
        command.add_argument("--notes")
        if action == "update":
            command.add_argument("--clear-merchant", action="store_true")
            command.add_argument("--clear-payment-method", action="store_true")
            command.add_argument("--clear-notes", action="store_true")
    commands.add_parser("list", help="List saved transactions")
    for action in ("get", "delete"):
        commands.add_parser(action).add_argument("id", type=int)
    args = parser.parse_args()
    try:
        store = TransactionStore(args.db)
        if args.command == "init":
            result = {"database": str(store.database_path), "status": "ready"}
        elif args.command in ("summary", "categories", "payments", "compare"):
            records = store.retrieve_transactions()
            if args.command == "summary":
                result = summarize(records, args.period, args.as_of)
            elif args.command == "compare":
                result = compare_periods(records, args.period, args.as_of)
            else:
                group = "category" if args.command == "categories" else "payment_method"
                result = spending_by(records, group, args.period, args.as_of)
        elif args.command == "record":
            result = store.create_transaction(**parse_transaction(args.message))
            print(f"Saved transaction #{result['id']}: CNY {result['amount']} | "
                  f"{result['category']} | {result['transaction_date']}")
        elif args.command in ("add", "update"):
            fields = ("amount", "category", "currency", "merchant", "payment_method",
                      "transaction_date", "notes")
            values = {key: getattr(args, key) for key in fields if getattr(args, key) is not None}
            if args.command == "add":
                result = store.create_transaction(**values)
            else:
                for key in ("merchant", "payment_method", "notes"):
                    if getattr(args, f"clear_{key}"):
                        if key in values:
                            raise ValueError(f"Cannot both set and clear {key}.")
                        values[key] = None
                result = store.update_transaction(args.id, **values)
        elif args.command == "list":
            result = store.retrieve_transactions()
        elif args.command == "get":
            result = store.get_transaction(args.id)
            if result is None:
                raise KeyError(f"Transaction {args.id} not found.")
        else:
            if not store.delete_transaction(args.id):
                raise KeyError(f"Transaction {args.id} not found.")
            result = {"deleted": args.id}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, sqlite3.Error, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
