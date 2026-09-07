"""Create ignored integration artifacts when tests start from a clean checkout."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from frtb_engine.database import database_path
from frtb_engine.ima_pipeline import run_ima
from scripts.build_report import build_report


ROOT = Path(__file__).resolve().parents[1]


def _integration_artifacts_are_ready() -> bool:
    ima_pointer = ROOT / "outputs/latest_ima_run.txt"
    sa_pointer = ROOT / "outputs/latest_run.txt"
    database = database_path()
    if not (ima_pointer.exists() and sa_pointer.exists() and database.exists()):
        return False

    ima_run = ROOT / "outputs" / ima_pointer.read_text(encoding="utf-8").strip()
    sa_run = ROOT / "outputs" / sa_pointer.read_text(encoding="utf-8").strip()
    required = (
        ima_run / "27_combined_capital_summary.json",
        ima_run / "FRTB_Market_Risk_Report.xlsx",
        sa_run / "16_capital_summary.json",
    )
    if not all(path.exists() for path in required):
        return False

    try:
        with sqlite3.connect(database) as connection:
            return connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    except sqlite3.DatabaseError:
        return False


def pytest_sessionstart(session) -> None:  # noqa: ARG001
    """Run the integrated engine once when ignored outputs are not available."""
    if _integration_artifacts_are_ready():
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_ima(f"IMA_TEST_{stamp}")
    build_report()
