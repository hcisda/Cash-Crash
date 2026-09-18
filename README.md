# Cash Crash

**Your AI-powered personal spending assistant**

Portfolio prototype with deterministic, rule-based natural-language parsing;
no external LLM or AI API is used. The web app now defaults to **Demo Mode**.
See [public demo and publishing instructions](docs/portfolio-demo.md).

Cash Crash converts short spending messages into validated transaction records,
calculates spending summaries, and visualizes category, payment and time trends.
The public application is a portfolio demo, not a production financial service.

## Portfolio architecture

**Natural-language input → transaction parsing → validation → storage → analytics → visualization**

| Layer | Implementation |
| --- | --- |
| Input and review | Streamlit message box and preview in entry_ui.py |
| Transaction parsing | Deterministic English keyword/date rules in parser.py |
| Validation | Shared category, payment, amount and date rules in rules.py |
| Storage | SQLite CRUD in storage.py; isolated temporary databases in demo.py |
| Analytics | Exact monetary totals, breakdowns and period comparisons in analytics.py |
| Visualization | Streamlit cards/tables and Altair charts in dashboard.py |

## Core features and technology stack

- Natural-language spending entry with review-before-save and useful errors.
- Today/week/month totals, category/payment breakdowns and spending trends.
- Week-over-week variance and category insights.
- Isolated fictional demo data, Reset Demo and an optional persistent local mode.

Stack: **Python, Streamlit, SQLite, Altair, rule-based natural-language parsing,
data validation and financial analytics**. No model, API key or bank connection
is required. Python supplies sqlite3; it must not be installed from PyPI.

## Run the portfolio demo locally

Use a fresh virtual environment (Python 3.13 is the reviewed version):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run streamlit_app.py
```

On macOS/Linux use `.venv/bin/python` instead. Community Cloud uses the root
requirements.txt; choose streamlit_app.py and Python 3.13. No packages.txt or
secrets configuration is needed. See the [official dependency guidance](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies).

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Use **streamlit_app.py** for public deployment. Each visitor gets isolated,
temporary, fictional SQLite data. Reset Demo restores their original samples.
Personal mode requires CASH_CRASH_MODE=local and dashboard.py on your computer.
Build a source-only publication ZIP with `python tools/build_public_demo.py`;
do not upload this entire workspace or the personal database.

Business rules, persistent transaction storage, and a deterministic spending parser. This is a
single-user local Python application with a small command-line interface for
testing and a local Streamlit dashboard for visual review. Deterministic analytics
are included. LLM/API parsing and weekly reporting are not built yet.

## Requirements and setup

Python 3.10 or newer. The CLI needs no third-party packages or API keys.
The dashboard uses Streamlit and Altair from requirements.txt.
Open a terminal in this project folder and run:

```powershell
python -m spending_agent init
```

This creates `data/spending.sqlite3` if needed. Existing records are preserved.
Any other command also initializes the database if it does not exist.

## Project structure

| File | Purpose |
| --- | --- |
| `streamlit_app.py` | Public entrypoint, always forces Demo Mode |
| `spending_agent/demo.py` | Per-session temporary database, samples, mode selection and reset |
| `tests/test_demo.py` | Isolation, reset, public UI and package exclusions |
| `tools/build_public_demo.py` | Builds a public source-only ZIP using an allowlist |
| `.streamlit/config.toml` | Theme; disables static file serving and usage telemetry |
| `docs/portfolio-demo.md` | Deployment, privacy boundaries and local mode instructions |
| `dashboard.py` | Streamlit dashboard; displays existing analytics results |
| `spending_agent/entry_ui.py` | Message preview, save confirmation and session draft handling |
| `requirements.txt` | Dashboard dependencies, including tested Streamlit version |
| `spending_agent/__init__.py` | Defines the Python package |
| `spending_agent/rules.py` | Categories, payment methods, defaults and validation |
| `spending_agent/parser.py` | Deterministic English spending-message extraction |
| `spending_agent/analytics.py` | Exact totals, breakdowns and period comparisons |
| `spending_agent/storage.py` | SQLite table and create/read/update/delete operations |
| `spending_agent/__main__.py` | Command-line entry point; calls the storage layer |
| `tests/test_storage.py` | Business-rule, CRUD and process-restart tests |
| `tests/test_parser.py` | Parser examples, invalid inputs and record-command persistence |
| `tests/test_analytics.py` | Known-data totals, variances, dates and analytics command tests |
| `tests/test_dashboard.py` | Dashboard empty/populated states, refresh and trend tests |
| `tests/test_entry_workflow.py` | Preview/save, invalid input, retry and duplicate-rerun checks |
| `data/spending.sqlite3` | Local persistent database, created when run |
| `.gitignore` | Keeps private database files and Python caches out of Git |
| `README.md` | Setup, business rules and manual test instructions |

The interface calls storage, which validates records using the business rules.
The dashboard reads storage and delegates calculations to analytics. Future AI
modules can use the same storage functions. No separate
web server or database server is required. Synced files under `sources/` are
read-only reference material and are not used or changed by this application.

## Business rules

- One call or command creates one transaction.
- Amount and category are required. Amount must be positive with at most two
  decimal places; refunds and zero-value records are outside this version.
- Currency defaults to CNY. Only CNY is supported in this MVP.
- Categories: Dining, Transport, Shopping, Entertainment, Housing, Utilities,
  Health, Education, Travel, Other.
- Payment methods: WeChat Pay, Alipay, Bank Card, Cash, Other. Missing payment
  method is stored as empty (`null`), rather than guessing a method.
- Merchant and notes may be empty. Whitespace-only text becomes `null`.
- Missing or empty transaction date defaults to today's date in Asia/Shanghai
  (UTC+08:00). Supplied dates must be real calendar dates in YYYY-MM-DD format.
- Creation and last-update timestamps are generated in UTC. Updating a record
  keeps its ID and creation time. An update with no changes leaves it untouched.
- Identical entries are allowed: two equal purchases can be legitimate.
- Deletion permanently removes the specified record; there is no undo yet.

## Database design

SQLite stores the `transactions` table in a file that survives command exits,
terminal closures and computer restarts. Each operation opens a connection,
commits successful changes (or rolls back errors), then closes the connection.

The default path is based on the project location, not the terminal's current
directory. To use another database, put `--db PATH` before the command:

```powershell
python -m spending_agent --db data/manual-test.sqlite3 init
```

Use the same database path on later commands to retrieve those records.
To back up this local database, copy the file while no commands are running.
It is a regular local file, not an encrypted vault or a cloud backup.

| Public field | SQLite column/type | Meaning |
| --- | --- | --- |
| id | id / INTEGER | Automatically assigned unique identifier |
| amount | amount_minor / INTEGER | Stored in fen; 35.00 yuan becomes 3500 |
| currency | currency / TEXT | CNY |
| category | category / TEXT | Required allowed category |
| merchant | merchant / TEXT, nullable | Merchant if known |
| payment_method | payment_method / TEXT, nullable | Allowed method if known |
| transaction_date | transaction_date / TEXT | Spending date, YYYY-MM-DD |
| notes | notes / TEXT, nullable | Optional description |
| created_at | created_at / TEXT | UTC creation timestamp |
| updated_at | updated_at / TEXT | UTC last-update timestamp |

The public functions and command output expose `amount` as an exact decimal
string such as `"35.00"`. Internally, integer fen avoids floating-point rounding.
The database also enforces positive integer amounts, CNY, valid categories and
valid payment methods. Date and text validation happens in Python. User values
are passed as SQL parameters rather than inserted into SQL text.

## Manual test: add, restart and retrieve

You can now save a simple natural-language expense directly:

```powershell
python -m spending_agent record "Lunch 35 WeChat"
python -m spending_agent list
```

The record command prints a saved confirmation followed by the complete saved
record. It saves immediately after validation, without a separate review prompt.
Use the existing update/delete commands to correct a saved interpretation.

### How the parser works

`parse_transaction(message)` in `parser.py` returns fields for the existing
`create_transaction` function. It does not write to the database itself.

1. Recognize today, yesterday or an explicit YYYY-MM-DD date. No date means
   today using the existing Shanghai timezone rule.
2. Map payment words to the existing allowed names: WeChat/WeChat Pay, Alipay,
   bank/credit/debit card/card, cash, and "other payment". Missing means null.
3. Require exactly one positive numeric amount, with up to two decimal places.
4. Match whole-word category keywords, such as lunch → Dining, taxi → Transport
   and coat → Shopping. Unrecognized descriptions become Other.
5. Recognize Starbucks, Uber and DiDi, or an explicit "at Corner Cafe" phrase,
   as merchants. Otherwise leave merchant null. Do not infer a merchant from
   a generic expense description.
6. Keep the original sentence in notes, then run the existing shared validation.
   The record command passes the result to the unchanged SQLite storage layer.

Examples, assuming today is 2026-09-17 (all amounts are CNY):

| Message | Amount | Category | Merchant | Payment | Date |
| --- | --- | --- | --- | --- | --- |
| Lunch 35 WeChat | 35.00 | Dining | null | WeChat Pay | 2026-09-17 |
| Starbucks 28 Alipay | 28.00 | Dining | Starbucks | Alipay | 2026-09-17 |
| Taxi 46 | 46.00 | Transport | null | null | 2026-09-17 |
| Bought a coat for 699 yesterday | 699.00 | Shopping | null | null | 2026-09-16 |

This first parser handles simple English expense entries, not arbitrary natural
language. It uses no LLM, external API, API key or additional package. Rules are
easy to inspect and test for the supported examples. Multiple numbers (including
quantities), conflicting category/payment/date cues, invalid amounts and detected
unsupported date/currency expressions produce errors without saving. Use `add`
with explicit fields for complex entries. Comma-separated amounts and spelled-out
numbers are not supported. Category/merchant vocabulary is deliberately small;
unknown descriptions may become Other, and not every unsupported phrasing can be
detected. Review the printed fields. Repeating a successful command saves another
transaction, consistent with the existing storage rules.

### Adding with explicit fields

From the project folder:

```powershell
python -m spending_agent add --amount 35 --category Dining --merchant "Lunch cafe" --payment-method "WeChat Pay" --notes "Lunch"
```

The output shows the saved record, including its ID and today's date. Each
command starts and exits the application. Close the terminal, open a new one in
this project folder, and run:

```powershell
python -m spending_agent list
```

Your saved lunch should still appear. To retrieve just that record, replace `1`
below with the ID printed by the add command:

```powershell
python -m spending_agent get 1
```

Additional examples (also replace `1` with your actual ID):

```powershell
python -m spending_agent update 1 --amount 38 --notes "Corrected lunch amount"
python -m spending_agent update 1 --clear-merchant
python -m spending_agent add --amount 699 --category Shopping --date 2026-09-16 --notes "Coat"
python -m spending_agent delete 1
python -m spending_agent --help
```

Updates change only supplied fields. Use `--clear-merchant`,
`--clear-payment-method` or `--clear-notes` to clear optional fields.
Missing records produce an error for get/update/delete commands.

## Storage functions

Create a `TransactionStore` with an optional database path, then use:

- `create_transaction(amount="35", category="Dining", ...)`: returns the saved record.
- `get_transaction(id)`: returns one record, or `None` if missing.
- `retrieve_transactions()`: returns all records, newest spending date first.
- `update_transaction(id, amount="38", ...)`: returns the updated record;
  raises `KeyError` if missing and `ValueError` for invalid fields.
- `delete_transaction(id)`: returns `True` if deleted, `False` if missing.

## Spending analytics

```powershell
python -m spending_agent summary --period today
python -m spending_agent summary --period week
python -m spending_agent categories --period month
python -m spending_agent payments --period month
python -m spending_agent compare --period week
python -m spending_agent compare --period month
```

See [analytics documentation](docs/analytics.md) for date-window definitions,
calculation rules, hand-checked sample totals and portfolio skills. Comparisons
use corresponding elapsed days of the prior period; output includes both ranges.

## Running the tests

Install requirements.txt first to include the dashboard tests.

```powershell
python -m unittest discover -s tests -v
```

Tests use temporary databases and do not change your spending database. The
restart test adds a record in one Python process, waits for it to exit, then
reads the record in another process. It also checks updates and deletion across
processes. Other tests cover defaults, exact amounts, validation, allowed
categories/payment methods, sorting and preservation of data after invalid edits.

## Launch the local dashboard

From the project folder:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run dashboard.py --server.address localhost
```

Open http://localhost:8501 in your browser if it does not open automatically.
Keep the terminal running; Ctrl+C stops the dashboard. After this one-time launch,
review spending and refresh data in the browser without using CLI commands.

In explicit LOCAL PERSONAL MODE, the dashboard reads the same data/spending.sqlite3 as the command-line app.
Set `$env:CASH_CRASH_MODE = "local"` before running dashboard.py to use that mode.
Otherwise the dashboard uses a private temporary demo dataset. The public
streamlit_app.py entrypoint always uses demo data, regardless of environment settings.
For a different database, set `$env:SPENDING_DATABASE = "C:\path\spending.sqlite3"`
in PowerShell before launching. The dashboard can now record expenses through a
conversational message box; existing records are not edited or deleted here.

### Record spending in the browser

1. Near the top, find **Tell me what you spent**, above the summary cards.
2. Type **Lunch 35 WeChat** in **Your spending message**.
3. Click **Review expense** to see the parsed amount, category, date, merchant,
   payment method and original message. Nothing is saved at this point.
4. Click **Record expense**. A confirmation appears and all totals, charts,
   insights and recent transactions refresh immediately.

Submit a revised message to replace a preview, or click **Discard preview**.
Unsafe input shows the parser's explanation and removes any older draft.
Unknown merchant/payment values remain empty in SQLite; omitted dates use today.
The existing parser validates fields, and storage validates again when saving.
No LLM or network service is used.

The save callback consumes the pending draft before writing, and removes the
Record button after success. Refreshes and other Streamlit reruns cannot save
the same draft again. A failed write restores the draft for retry. This guards
normal session reruns, not cross-device submissions or a process crash after
commit. Intentionally reviewing and recording the same message again creates
another expense. Manual structured entry remains available through the optional
CLI add command; everyday natural-language entry works entirely in the browser.

- Cards: today's, this week's and this month's recorded spending; week-over-week
  percentage change and amount change. N/A means a zero previous-week baseline.
- Category chart: current month-to-date totals, with amount/share tooltips.
- Trend: daily totals across the last 30 or 90 days, including zero-spending days.
- Payment chart: month-to-date totals including Unknown for missing methods.
- Insights: leading monthly categories, largest weekly category increase in yuan,
  and the weekly comparison. Ties are preserved.
- Recent table: latest 50 saved transactions by spending date across all periods.
  Future-dated records appear in the table but are excluded from current totals.

Weekly comparisons use the existing matching-weekday rules; both windows are
displayed. Refresh data reloads SQLite with no cache. Monetary calculations stay
in analytics.py using integer fen; conversion to floating point is only for chart
coordinates. Currency strings in cards, tables and tooltips keep exact cents.

The dashboard uses summarize(), spending_by(), compare_periods(), and the new
daily_spending() function. There is no duplicated aggregation in dashboard.py.
Empty data produces zero cards, helpful messages and a zero daily trend.

Portfolio skills: BI dashboard design, KPI presentation, time-series and category
visualization, shared metric definitions, variance explanations and UI validation
against known financial data. No cloud deployment or authentication is configured.
