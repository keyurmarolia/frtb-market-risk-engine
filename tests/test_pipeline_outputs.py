import json
import zipfile
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def latest_run() -> Path:
    run_id = (PROJECT_ROOT / "outputs/latest_run.txt").read_text(encoding="utf-8").strip()
    return PROJECT_ROOT / "outputs" / run_id


def test_latest_completed_run_reconciles_capital_and_rwa() -> None:
    summary = json.loads((latest_run() / "16_capital_summary.json").read_text(encoding="utf-8"))
    parts = summary["sbm_capital_inr"] + summary["drc_capital_inr"] + summary["rrao_capital_inr"]
    assert summary["frtb_sa_capital_inr"] == parts
    assert summary["market_rwa_inr"] == summary["frtb_sa_capital_inr"] * 12.5


def test_portable_report_has_formulas_and_neutral_metadata() -> None:
    ima_id = (PROJECT_ROOT / "outputs/latest_ima_run.txt").read_text(encoding="utf-8").strip()
    report = PROJECT_ROOT / "outputs" / ima_id / "FRTB_Market_Risk_Report.xlsx"
    assert report.exists()
    with zipfile.ZipFile(report) as archive:
        names = set(archive.namelist())
        core = archive.read("docProps/core.xml").decode("utf-8").lower()
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        formulas = "".join(
            archive.read(name).decode("utf-8")
            for name in names if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
    assert "frtb market risk engine" in core
    assert "Overview" in workbook and "Checks" in workbook and "Sources" in workbook
    assert "<f>" in formulas


def test_latest_run_preserves_all_intermediate_stages() -> None:
    manifest = json.loads((latest_run() / "run_manifest.json").read_text(encoding="utf-8"))
    stages = {artifact["stage"] for artifact in manifest["artifacts"]}
    assert len(stages) == 16
    assert {"01_trades", "03_delta_trade_level", "10_sbm_scenarios", "14_drc_summary", "15_rrao_detail", "capital_summary"}.issubset(stages)


def test_all_seven_sbm_classes_are_visible_in_output() -> None:
    classes = pd.read_csv(latest_run() / "09_sbm_class_results.csv")
    assert classes["risk_class"].nunique() == 7
    assert set(classes["risk_measure"]) == {"DELTA", "VEGA", "CURVATURE"}
