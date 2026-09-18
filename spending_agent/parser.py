"""Small, deterministic English expense parser; no network calls or storage."""

import re
from datetime import date, timedelta

from .rules import today, validate_transaction

CATEGORY_KEYWORDS = {
    "Dining": ("lunch", "dinner", "breakfast", "coffee", "restaurant", "starbucks"),
    "Transport": ("taxi", "bus", "subway", "metro", "uber", "didi"),
    "Shopping": ("coat", "clothes", "shirt", "shoes", "shopping"),
    "Entertainment": ("cinema", "movie", "concert", "entertainment"),
    "Housing": ("rent", "housing"),
    "Utilities": ("electricity", "water bill", "internet bill", "utilities"),
    "Health": ("medicine", "pharmacy", "doctor", "hospital", "health"),
    "Education": ("tuition", "course", "textbook", "education"),
    "Travel": ("hotel", "flight", "travel"),
}
PAYMENT_ALIASES = {
    "WeChat Pay": r"\bwechat(?:\s+pay)?\b",
    "Alipay": r"\balipay\b",
    "Bank Card": r"\b(?:bank\s+card|credit\s+card|debit\s+card|card)\b",
    "Cash": r"\bcash\b",
    "Other": r"\bother\s+payment\b",
}
KNOWN_MERCHANTS = {"starbucks": "Starbucks", "uber": "Uber", "didi": "DiDi"}


def parse_transaction(message, *, reference_date=None):
    """Return validated fields accepted by TransactionStore.create_transaction.

    reference_date is an optional date for reproducible tests. In normal use,
    the shared Shanghai-date rule determines today. Ambiguity raises ValueError.
    """
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Enter one spending sentence with an amount.")
    original = message.strip()
    text = original
    if re.search(r"[$€£]|\b(?:USD|EUR|GBP|HKD|JPY|dollars?|euros?|pounds?)\b", text, re.I):
        raise ValueError("Only CNY expenses are supported. Use the add command for explicit fields.")
    if re.search(r"\b(?:refund\w*|returned|income|received|owe|not|didn't)\b", text, re.I):
        raise ValueError("Enter a completed positive expense, without refunds or negation.")
    if re.search(r"\b(?:tomorrow|last|ago|monday|tuesday|wednesday|thursday|friday|saturday|sunday|january|february|march|april|may|june|july|august|september|october|november|december)\b", text, re.I):
        raise ValueError("Use today, yesterday, or a YYYY-MM-DD date.")

    base_date = reference_date if reference_date is not None else date.fromisoformat(today())
    date_matches = list(re.finditer(r"\b(?:today|yesterday|\d{4}-\d{2}-\d{2})\b", text, re.I))
    if len(date_matches) > 1:
        raise ValueError("Use only one transaction date per message.")
    spending_date = base_date.isoformat()
    if date_matches:
        match = date_matches[0]
        token = match.group().lower()
        spending_date = ((base_date - timedelta(days=1)).isoformat() if token == "yesterday"
                         else base_date.isoformat() if token == "today" else token)
        text = text[:match.start()] + " " + text[match.end():]

    payments = [name for name, pattern in PAYMENT_ALIASES.items() if re.search(pattern, text, re.I)]
    if len(payments) > 1:
        raise ValueError("Multiple payment methods found. Enter one transaction at a time.")
    for pattern in PAYMENT_ALIASES.values():
        text = re.sub(pattern, " ", text, flags=re.I)

    # Collect complete numeric tokens, including malformed ones, so 35.999,
    # -35, or 1,000 cannot silently become a different valid amount.
    amounts = list(re.finditer(r"[+-]?(?:\d[\d.,]*\d|\d|\.\d+)", text))
    if len(amounts) != 1:
        raise ValueError("Provide exactly one numeric amount for one expense; use add for complex entries.")
    match = amounts[0]
    amount = match.group()
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", amount):
        raise ValueError("Use a positive amount like 35 or 35.50, without commas.")
    # Reject attached units such as 35k rather than recording 35 yuan.
    before, after = text[:match.start()], text[match.end():]
    if (before and before[-1].isalnum() and not re.search(r"(?:CNY|RMB)$", before, re.I)) or (
        after and after[0].isalnum() and not re.match(r"(?:yuan|CNY|RMB)\b", after, re.I)
    ):
        raise ValueError("Separate the amount from words, or use CNY/RMB/yuan.")
    description = before + " " + after
    description = re.sub(r"\b(?:CNY|RMB|yuan)\b|[¥￥]", " ", description, flags=re.I)

    # Only explicit 'at Merchant' phrases or a small known list identify a
    # merchant. 'Lunch' and 'coat' are descriptions, never merchant guesses.
    merchant = None
    merchant_match = re.search(
        r"\bat\s+(.+?)(?=\s+\b(?:for|using|via|with|paid|on)\b|$)", description, re.I,
    )
    category_text = description
    if merchant_match:
        merchant = merchant_match.group(1).strip(" .,;:") or None
        category_text = description[:merchant_match.start()] + " " + description[merchant_match.end():]
    else:
        known = [name for keyword, name in KNOWN_MERCHANTS.items()
                 if re.search(r"\b" + re.escape(keyword) + r"\b", description, re.I)]
        if len(known) > 1:
            raise ValueError("Multiple merchants found. Enter one expense at a time.")
        merchant = known[0] if known else None
    categories = [category for category, keywords in CATEGORY_KEYWORDS.items()
                  if any(re.search(r"\b" + re.escape(word) + r"\b", category_text, re.I)
                         for word in keywords)]
    if len(categories) > 1:
        raise ValueError("Multiple spending categories found. Use add to specify the category.")
    category = categories[0] if categories else "Other"
    if category == "Other" and merchant == "Starbucks":
        category = "Dining"

    normalized = validate_transaction({
        "amount": amount, "currency": "CNY", "category": category,
        "merchant": merchant, "payment_method": payments[0] if payments else None,
        "transaction_date": spending_date, "notes": original,
    })
    fen = normalized.pop("amount_minor")
    normalized["amount"] = f"{fen // 100}.{fen % 100:02d}"
    return normalized
