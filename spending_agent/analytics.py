"""Pure spending calculations over records returned by the storage layer.

No database connections or writes here. All money is summed as integer fen.
"""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from .rules import today


def period_ranges(period, as_of=None):
    """Inclusive current-to-date and corresponding previous-period ranges."""
    end = date.fromisoformat(as_of or today())
    if period == "today":
        start = end
        previous_start = previous_end = end - timedelta(days=1)
    elif period == "week":
        start = end - timedelta(days=end.weekday())  # Monday is day zero.
        previous_start = start - timedelta(days=7)
        previous_end = end - timedelta(days=7)
    elif period == "month":
        start = end.replace(day=1)
        previous_last = start - timedelta(days=1)
        previous_start = previous_last.replace(day=1)
        previous_end = previous_last.replace(day=min(end.day, previous_last.day))
    else:
        raise ValueError("Period must be today, week or month.")
    return start, end, previous_start, previous_end


def _money(fen):
    sign = "-" if fen < 0 else ""
    whole, fraction = divmod(abs(fen), 100)
    return f"{sign}{whole}.{fraction:02d}"


def _percentage(change, baseline):
    if baseline == 0:
        return None  # Percentage change from zero is undefined.
    return str((Decimal(change) * 100 / Decimal(baseline)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP,
    ))


def _aggregate(transactions, start, end):
    total = count = 0
    categories, payments = {}, {}
    for record in transactions:
        if not start.isoformat() <= record["transaction_date"] <= end.isoformat():
            continue
        if record["currency"] != "CNY":
            raise ValueError("Analytics supports CNY records only.")
        fen = int(Decimal(record["amount"]) * 100)
        total += fen
        count += 1
        category = record["category"]
        payment = record["payment_method"] or "Unknown"
        categories[category] = categories.get(category, 0) + fen
        payments[payment] = payments.get(payment, 0) + fen
    return total, count, categories, payments


def _range(start, end):
    return {"start": start.isoformat(), "end": end.isoformat(),
            "days": (end - start).days + 1}


def _leaders(totals):
    if not totals or max(totals.values()) <= 0:
        return []
    largest = max(totals.values())
    return [name for name in sorted(totals) if totals[name] == largest]


def summarize(transactions, period="month", as_of=None):
    """Total and all tied highest-spending categories for one period."""
    start, end, _, _ = period_ranges(period, as_of)
    total, count, categories, _ = _aggregate(transactions, start, end)
    return {
        "period": period, "date_range": _range(start, end), "currency": "CNY",
        "total": _money(total), "transaction_count": count,
        "highest_spending_categories": _leaders(categories),
        "highest_category_amount": _money(max(categories.values(), default=0)),
    }


def spending_by(transactions, group="category", period="month", as_of=None):
    """Category or payment totals, descending by amount, then alphabetically."""
    if group not in ("category", "payment_method"):
        raise ValueError("Group must be category or payment_method.")
    start, end, _, _ = period_ranges(period, as_of)
    total, count, categories, payments = _aggregate(transactions, start, end)
    totals = categories if group == "category" else payments
    return {
        "period": period, "date_range": _range(start, end), "currency": "CNY",
        "total": _money(total), "transaction_count": count, "group_by": group,
        "groups": [{group: name, "amount": _money(amount),
                    "share_percent": _percentage(amount, total)}
                   for name, amount in sorted(totals.items(), key=lambda item: (-item[1], item[0]))],
    }


def compare_periods(transactions, period="week", as_of=None):
    """Compare period-to-date to the same elapsed days in the previous period.

    The previous month is capped at its last day when it is shorter. Ranges and
    day counts are returned so that this difference is visible to the user.
    """
    if period not in ("week", "month"):
        raise ValueError("Comparisons support week or month.")
    start, end, previous_start, previous_end = period_ranges(period, as_of)
    records = list(transactions)  # Both calculations use the same snapshot.
    total, count, categories, _ = _aggregate(records, start, end)
    previous, previous_count, previous_categories, _ = _aggregate(records, previous_start, previous_end)
    changes = {name: categories.get(name, 0) - previous_categories.get(name, 0)
               for name in categories.keys() | previous_categories.keys()}
    return {
        "period": period, "basis": "period-to-date vs corresponding prior-period days",
        "currency": "CNY", "current_range": _range(start, end),
        "previous_range": _range(previous_start, previous_end),
        "equal_day_counts": (end - start) == (previous_end - previous_start),
        "current_total": _money(total), "previous_total": _money(previous),
        "current_transaction_count": count, "previous_transaction_count": previous_count,
        "change_amount": _money(total - previous),
        "change_percent": _percentage(total - previous, previous),
        "highest_spending_categories": _leaders(categories),
        "highest_category_amount": _money(max(categories.values(), default=0)),
        "largest_increase_categories": _leaders(changes),
        "largest_increase_amount": _money(max(0, max(changes.values(), default=0))),
        "categories": [
            {"category": name, "current_amount": _money(categories.get(name, 0)),
             "previous_amount": _money(previous_categories.get(name, 0)),
             "change_amount": _money(change),
             "change_percent": _percentage(change, previous_categories.get(name, 0))}
            for name, change in sorted(changes.items(), key=lambda item: (-item[1], item[0]))
        ],
    }


def daily_spending(transactions, days=30, as_of=None):
    """Daily recorded spending, including zero days, through the reference date."""
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 366:
        raise ValueError("Trend days must be an integer between 1 and 366.")
    end = date.fromisoformat(as_of or today())
    start = end - timedelta(days=days - 1)
    totals = {(start + timedelta(days=offset)).isoformat(): 0 for offset in range(days)}
    for record in transactions:
        day = record["transaction_date"]
        if day in totals:
            if record["currency"] != "CNY":
                raise ValueError("Analytics supports CNY records only.")
            totals[day] += int(Decimal(record["amount"]) * 100)
    return {"currency": "CNY", "date_range": _range(start, end),
            "total": _money(sum(totals.values())),
            "days": [{"date": day, "amount": _money(amount)} for day, amount in totals.items()]}
