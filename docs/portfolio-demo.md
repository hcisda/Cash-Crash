# Cash Crash: public portfolio demo

Cash Crash converts natural-language spending entries into structured transaction
data, performs automated spending analytics, and visualizes financial trends.
The parser is rule-based: no external LLM, API key, bank or payment integration.

## Run or deploy the public demo

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Use **streamlit_app.py** as the Streamlit deployment entrypoint. This entrypoint
forces Demo Mode even if CASH_CRASH_MODE or SPENDING_DATABASE is set on the server.
dashboard.py also defaults to demo, but it supports the explicit local opt-in.
Do not set personal database paths or secrets on the public host.

Each browser session owns a DemoSession object in Streamlit session_state, with
a unique TemporaryDirectory and SQLite file. There is no global store, shared
cache, visitor-chosen database path, login or cross-session data browser. Ten
fictional records cover Dining, Transport, Shopping and Entertainment, multiple
payment methods, and current/prior weeks. Dates are relative to session creation.

Visitors can review and record fictional expense messages. Reset Demo replaces
only their database with the original sample values and dates, clearing draft
and confirmation state. IDs restart; generated audit timestamps are new. A new
browser session starts fresh. Session reload/loss and app restart can lose data.
Temporary files are cleaned up when their objects are released. An abrupt process
exit can leave orphan files in the host temp directory; no session reuses them.
This is application-level session isolation, not encrypted financial storage or
a production multi-tenant security system. Do not enter sensitive information.

## Publish only the source package

```powershell
python tools/build_public_demo.py
```

This produces **dist/cash-crash-public.zip** from an explicit source-file
allowlist. Extract it into a fresh folder and use those files for a NEW public
GitHub repository. Do not upload the original project directory, data folder,
synced sources, or local database. Streamlit deployment should use this fresh
source-only repository and streamlit_app.py.

.gitignore excludes data/, SQLite files, .env files, secrets.toml, private key
files, virtual environments and synced project sources. The package does not
include them even if they exist locally. Static file serving is disabled.
Git ignores do not remove files from existing commit history: if you ever publish
from another repository that already tracked private data, its history requires
separate review. The original workspace was not a Git repository at preparation.

No API keys or account credentials are required. The archive includes only the
listed source, tests, configuration and documentation. No application is deployed
automatically by the packaging command.

## Keep using personal mode locally

```powershell
$env:CASH_CRASH_MODE = "local"
python -m streamlit run dashboard.py --server.address localhost
```

This uses data/spending.sqlite3, or an explicitly configured SPENDING_DATABASE.
The CLI remains unchanged and still uses persistent local storage. Never deploy
personal mode publicly. To return dashboard.py to its safe default:

```powershell
Remove-Item Env:CASH_CRASH_MODE
```

## Portfolio story

- Python / Streamlit / SQLite: a complete interactive data application.
- Natural-language parsing and validation: consistent records from short messages.
- Financial analytics: precise totals, category mix and comparable-period variance.
- Data visualization: summary cards, trend charts and category/payment breakdowns.
- Product design: review-before-save, helpful errors, isolation and resettable demos.

The requested AI-powered subtitle is accompanied by an explicit rule-based parser
disclosure. Describe the current implementation accurately in interviews.
