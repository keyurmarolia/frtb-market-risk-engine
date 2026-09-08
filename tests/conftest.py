"""Create ignored integration artifacts when tests start from a clean checkout."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import json
import hashlib

from frtb_engine.database import database_path
from frtb_engine.ima_pipeline import run_ima
from frtb_engine.provenance import calculation_fingerprint
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
        manifest = json.loads((ima_run / "run_manifest.json").read_text())
        if manifest.get("calculation_fingerprint") != calculation_fingerprint():
            return False
        summary = json.loads((ima_run / "27_combined_capital_summary.json").read_text())
        if summary["sa_run_id"] != sa_run.name:
            return False
        for run in (ima_run, sa_run):
            saved = json.loads((run / "run_manifest.json").read_text())
            for artifact in saved["artifacts"]:
                path = ROOT / artifact["path"]
                if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
                    return False
        with sqlite3.connect(database) as connection:
            runs = {row[0] for row in connection.execute("SELECT run_id FROM engine_runs WHERE status='completed'")}
            return {ima_run.name, sa_run.name}.issubset(runs) and connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    except (sqlite3.DatabaseError, OSError, KeyError, ValueError):
        return False


def pytest_sessionstart(session) -> None:  # noqa: ARG001
    """Run the integrated engine once when ignored outputs are not available."""
    if _integration_artifacts_are_ready():
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_ima(f"IMA_TEST_{stamp}")
    build_report()
