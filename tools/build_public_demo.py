"""Build a source-only public ZIP from an explicit allowlist, never workspace data."""

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = [
    "streamlit_app.py", "dashboard.py", "requirements.txt", ".gitignore", ".streamlit/config.toml",
    "README.md", "docs/analytics.md", "docs/portfolio-demo.md",
    "spending_agent/__init__.py", "spending_agent/__main__.py", "spending_agent/rules.py",
    "spending_agent/storage.py", "spending_agent/parser.py", "spending_agent/analytics.py",
    "spending_agent/entry_ui.py", "spending_agent/demo.py",
    "tests/test_storage.py", "tests/test_parser.py", "tests/test_analytics.py",
    "tests/test_dashboard.py", "tests/test_entry_workflow.py", "tests/test_demo.py",
    "tools/build_public_demo.py",
]


def build(destination=None):
    destination = Path(destination) if destination else ROOT / "dist" / "cash-crash-public.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for name in PUBLIC_FILES:
            archive.write(ROOT / name, name)
    return destination


if __name__ == "__main__":
    print(build())
