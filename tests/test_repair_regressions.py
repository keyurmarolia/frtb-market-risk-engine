"""Regression cases for alternative desk treatment and reproducible artifacts."""

import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pandas as pd

from frtb_engine.database import DDL, initialise_database
from frtb_engine.ima_pipeline import _save_canonical_inputs
from frtb_engine.provenance import calculation_fingerprint


ROOT = Path(__file__).resolve().parents[1]


def test_all_desks_fall_back_to_sa_and_report_builds(tmp_path):
    shutil.copytree(ROOT / "config", tmp_path / "config")
    shutil.copy2(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    (tmp_path / "data/synthetic").mkdir(parents=True)
    for name in ("trades.csv", "market_data.yaml"):
        shutil.copy2(ROOT / "data/synthetic" / name, tmp_path / "data/synthetic" / name)
    program = """
from pathlib import Path
import frtb_engine.ima_pipeline as pipeline
from frtb_engine.config import PROJECT_ROOT
from scripts import build_report
original = pipeline.determine_desk_eligibility
def no_eligible_desks(*args):
    frame = original(*args)
    frame['ima_eligible'] = False
    frame['final_treatment'] = 'SA_FALLBACK'
    return frame
pipeline.determine_desk_eligibility = no_eligible_desks
summary = pipeline.run_ima('IMA_ALL_FALLBACK_TEST')
assert summary['eligible_desks'] == []
assert summary['eligible_sa_share'] == 0
assert summary['ima_eligible_capital_before_surcharge_inr'] == 0
assert summary['pla_amber_surcharge_inr'] == 0
assert summary['stress_window_start'] is None
assert summary['final_frtb_market_risk_capital_inr'] == summary['full_book_sa_capital_inr']
build_report.ROOT = PROJECT_ROOT
assert build_report.build_report().exists()
"""
    env = dict(os.environ, FRTB_PROJECT_ROOT=str(tmp_path),
               PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "src")]),
               PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-c", program], env=env, cwd=tmp_path,
                            text=True, capture_output=True, timeout=240)
    assert result.returncode == 0, result.stdout + result.stderr


def test_test_setup_rejects_changed_calculation(monkeypatch):
    import conftest
    monkeypatch.setattr(conftest, "calculation_fingerprint", lambda: "changed-source")
    assert not conftest._integration_artifacts_are_ready()


def test_fingerprint_changes_when_input_changes(tmp_path):
    shutil.copytree(ROOT / "config", tmp_path / "config")
    shutil.copytree(ROOT / "src", tmp_path / "src")
    shutil.copytree(ROOT / "scripts", tmp_path / "scripts")
    (tmp_path / "data/synthetic").mkdir(parents=True)
    shutil.copy2(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    for name in ("trades.csv", "market_data.yaml"):
        shutil.copy2(ROOT / "data/synthetic" / name, tmp_path / "data/synthetic" / name)
    before = calculation_fingerprint(tmp_path)
    path = tmp_path / "data/synthetic/market_data.yaml"
    path.write_text(path.read_text() + "\n# changed input snapshot\n")
    assert calculation_fingerprint(tmp_path) != before


def test_canonical_gzip_files_are_repeatable(tmp_path, monkeypatch):
    import frtb_engine.ima_pipeline as pipeline
    monkeypatch.setattr(pipeline, "PROJECT_ROOT", tmp_path)
    frame = pd.DataFrame({"value": [1.25, 2.5]})
    _save_canonical_inputs(frame, frame, frame, frame)
    target = tmp_path / "data/synthetic/ima"
    before = {p.name: p.read_bytes() for p in target.iterdir()}
    _save_canonical_inputs(frame, frame, frame, frame)
    assert before == {p.name: p.read_bytes() for p in target.iterdir()}
    for path in target.glob("*.gz"):
        assert path.read_bytes()[4:8] == b"\0\0\0\0"


def test_database_migrates_year_counts_without_changing_values(tmp_path):
    path = tmp_path / "older.sqlite3"
    old = DDL.replace("maturity_years REAL", "maturity_date TEXT").replace(
        "option_expiry_years REAL", "option_expiry TEXT")
    with sqlite3.connect(path) as connection:
        connection.executescript(old)
        connection.execute("INSERT INTO portfolios VALUES ('P','Test','India','INR','INR','synthetic')")
        connection.execute("""INSERT INTO trades(
            trade_id,portfolio_id,desk,sub_portfolio,instrument_type,product_form,
            trade_currency,reporting_currency,long_short,is_synthetic,source_label,
            maturity_date,option_expiry) VALUES(
            'T','P','Rates','Rates','BOND','cash','INR','INR','long',1,'synthetic','5.5','1.25')""")
    initialise_database(path)
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT maturity_years,option_expiry_years FROM trades").fetchone()
        columns = {r[1] for r in connection.execute("PRAGMA table_info(trades)")}
    assert row == (5.5, 1.25)
    assert "maturity_date" not in columns and "option_expiry" not in columns
