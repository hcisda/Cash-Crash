# Spending analytics

Run these commands from the project folder. They read the existing SQLite data;
no packages, API keys or database migration are needed.

```powershell
python -m spending_agent summary --period today
python -m spending_agent summary --period week
python -m spending_agent summary --period month
python -m spending_agent categories --period month
python -m spending_agent payments --period month
python -m spending_agent compare --period week
python -m spending_agent compare --period month
```

All commands default to month if --period is omitted. Add --as-of 2026-09-17 for
a reproducible reference date. Otherwise the shared Shanghai today rule applies.
The global --db option goes before the command when using another database file.
Outputs are labelled JSON with amounts as exact decimal strings.

## Calculation rules

The command reads records once using the existing storage layer and passes them
to pure functions in analytics.py. Those functions do not open or modify the
database. Reading all records is sufficient for this small, single-user MVP;
larger datasets could later benefit from date-filtered database queries.

- Today: that calendar date only.
- This week: Monday through the reference date, inclusive.
- This month: the first day through the reference date, inclusive.
- Future-dated entries are excluded. Spending dates, not creation timestamps,
  determine inclusion. All figures represent recorded spending only.
- Compare uses current period-to-date against corresponding days last week or
  month, not the entire prior period. A Thursday compares Monday–Thursday with
  the previous Monday–Thursday. September 17 compares September 1–17 with August
  1–17. Both date ranges and their day counts are printed.
- If the prior month is shorter, its end date is capped at its last day. For
  March 31 versus February 28, equal_day_counts is false; the totals cover
  different numbers of days and are not daily-average-adjusted.
- Money is converted from the storage layer's exact decimal strings into integer
  fen before summing; no floating-point money arithmetic is used.
- Change in yuan = current minus previous. Percentage = change / previous × 100,
  rounded half-up to two decimal places. Zero baseline means null (undefined),
  including when both totals are zero.
- Largest increase is ranked by positive yuan change, not percentage. If no
  category increased, the category list is empty and increase amount is 0.00.
- Highest spending uses the current period's category totals. All tied winners
  are returned alphabetically. Empty periods have no winners.
- Category comparisons include categories present in either period, treating
  missing categories as zero. Breakdowns include observed groups only, sorted by
  amount descending, then name. Missing payment methods form an Unknown group.
- Empty totals are 0.00 with zero transactions and empty breakdowns. Percentage
  shares may not sum to exactly 100.00 because each share is rounded separately.

Public functions: period_ranges(), summarize(), spending_by(), compare_periods().
They accept records from TransactionStore.retrieve_transactions(); the optional
as_of string selects the reference date for reproducible analysis.

## Hand-checked test fixture

Tests create these transactions in a temporary SQLite database. They do not add
sample spending to the personal database. Reference date: September 17, 2026.

| Date | CNY | Category | Payment |
| --- | ---: | --- | --- |
| August 1 | 80 | Dining | Cash |
| August 17 | 20 | Transport | Unknown |
| August 18 | 999 | Other | Cash |
| September 1 | 100 | Housing | Bank Card |
| September 7 | 20 | Dining | Cash |
| September 10 | 30 | Transport | Unknown |
| September 10 | 500 | Shopping | Alipay |
| September 14 | 35 | Dining | WeChat Pay |
| September 15 | 28 | Dining | Alipay |
| September 17 | 46 | Transport | Unknown |
| September 17 | 699 | Shopping | Alipay |
| September 18 | 999 | Other | Cash |

Manual reconciliation:

- Today: 46 + 699 = **745**.
- This week: 35 + 28 + 46 + 699 = **808**.
- Prior corresponding week: 20 + 30 + 500 = **550**.
- Weekly variance: 808 − 550 = **258**, or 258 / 550 × 100 = **46.91%**.
- Category increases: Dining 63 − 20 = **43**; Transport 46 − 30 = **16**;
  Shopping 699 − 500 = **199**. These sum to **258**.
- This month: 100 + 20 + 30 + 500 + 35 + 28 + 46 + 699 = **1458**.
- Prior corresponding month: 80 + 20 = **100**; variance **1358**, or **1358%**.
- Monthly categories: Dining 83 + Transport 76 + Shopping 1199 + Housing 100 = **1458**.
- Monthly payments: Cash 20 + Unknown 76 + Alipay 1227 + WeChat Pay 35 + Bank Card 100 = **1458**.

August 18 is outside the prior month comparison window; September 18 is beyond
the reference date. Both 999 entries are deliberately excluded.

## Tests and portfolio skills

Run: python -m unittest discover -s tests -v

Tests cover the fixture totals, breakdown reconciliation, positive and negative
variance, empty periods, zero baselines, ties, exact cents, calendar boundaries,
leap years, all four analytics commands, and unchanged stored records.

- Financial analysis: precise expense totals, category mix, payment reconciliation.
- Variance analysis: comparable date windows, absolute/percentage movements,
  identifying the categories responsible for changes, and zero-baseline handling.
- Business analytics: clear metric definitions, reproducible reference dates,
  data-quality assumptions, tested outputs and decision-useful summaries.
