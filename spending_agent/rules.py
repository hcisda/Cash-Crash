"""Shared business rules. No AI or database code belongs here."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

CATEGORIES = (
    "Dining", "Transport", "Shopping", "Entertainment", "Housing",
    "Utilities", "Health", "Education", "Travel", "Other",
)
PAYMENT_METHODS = ("WeChat Pay", "Alipay", "Bank Card", "Cash", "Other")
LOCAL_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
EDITABLE_FIELDS = {
    "amount", "currency", "category", "merchant", "payment_method",
    "transaction_date", "notes",
}


def today():
    return datetime.now(LOCAL_TIMEZONE).date().isoformat()


def validate_transaction(values):
    """Normalize a complete record and convert yuan into integer fen."""
    unknown = set(values) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {', '.join(sorted(unknown))}")
    try:
        amount = Decimal(str(values.get("amount", "")))
        if not amount.is_finite() or amount <= 0 or amount > Decimal("92233720368547758.07"):
            raise ValueError("Amount must be positive and fit in SQLite's integer range.")
        fen = amount * 100
        if fen != fen.to_integral_value():
            raise ValueError("Amount must have at most two decimal places.")
    except InvalidOperation as exc:
        raise ValueError("Amount must be a valid number.") from exc

    currency = values.get("currency", "CNY")
    if currency != "CNY":
        raise ValueError("This MVP supports CNY only.")
    category = values.get("category")
    if category not in CATEGORIES:
        raise ValueError(f"Category must be one of: {', '.join(CATEGORIES)}")
    payment = values.get("payment_method")
    if payment not in (None, "") and payment not in PAYMENT_METHODS:
        raise ValueError(f"Payment method must be one of: {', '.join(PAYMENT_METHODS)}")

    transaction_date = values.get("transaction_date") or today()
    try:
        if not isinstance(transaction_date, str):
            raise ValueError()
        parsed = date.fromisoformat(transaction_date)
        if parsed.isoformat() != transaction_date:
            raise ValueError()
    except ValueError as exc:
        raise ValueError("Transaction date must be a real date in YYYY-MM-DD format.") from exc

    result = {
        "amount_minor": int(fen), "currency": currency, "category": category,
        "payment_method": payment or None, "transaction_date": transaction_date,
    }
    for field in ("merchant", "notes"):
        value = values.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{field} must be text or empty.")
        result[field] = value.strip() or None if value is not None else None
    return result

