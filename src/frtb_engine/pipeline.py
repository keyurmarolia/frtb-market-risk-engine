"""End-to-end FRTB SA orchestration with immutable intermediate outputs."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import pandas as pd

from frtb_engine.config import PROJECT_ROOT, load_market_data, load_project_config
from frtb_engine.database import database_path, load_synthetic_book
from frtb_engine.drc import calculate_drc
from frtb_engine.parameters import risk_weight
from frtb_engine.pricing import price_trade_inr, price_trade_local
from frtb_engine.rrao import calculate_rrao
from frtb_engine.sbm import calculate_sbm
from frtb_engine.sensitivities import calculate_curvature, calculate_delta, calculate_vega, load_trades
from frtb_engine.validation import validate_foundation


def run_sa(run_id: str | None = None) -> Dict[str, float | str]:
    validate_foundation()
    load_counts = load_synthetic_book()
    trades = load_trades()
    market = load_market_data()
    valuations = _price_book(trades, market)
    delta = calculate_delta(trades, market)
    vega = calculate_vega(trades, market)
    curvature = calculate_curvature(trades, market, delta, risk_weight)
    sbm = calculate_sbm(delta, vega, curvature)
    drc = calculate_drc(trades, valuations, market)
    rrao = calculate_rrao(trades, market)
    total_capital = float(sbm["sbm_capital"] + drc["drc_capital"] + rrao["rrao_capital"])
    market_rwa = total_capital * 12.5
    resolved_run_id = run_id or datetime.now(timezone.utc).strftime("SA_%Y%m%dT%H%M%SZ")
    output_dir = PROJECT_ROOT / "outputs" / resolved_run_id
    if output_dir.exists():
        raise FileExistsError(f"Run directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    artifacts = {
        "01_trades": trades,
        "02_valuations": valuations,
        "03_delta_trade_level": delta,
        "04_vega_trade_level": vega,
        "05_curvature_trade_level": curvature,
        "06_delta_netted_weighted": sbm["weighted_delta"],
        "07_vega_netted_weighted": sbm["weighted_vega"],
        "08_sbm_bucket_results": sbm["bucket_results"],
        "09_sbm_class_results": sbm["class_results"],
        "10_sbm_scenarios": sbm["scenario_summary"],
        "11_drc_gross_jtd": drc["gross_jtd"],
        "12_drc_net_jtd": drc["net_jtd"],
        "13_drc_bucket_results": drc["bucket_results"],
        "14_drc_summary": drc["summary"],
        "15_rrao_detail": rrao["detail"],
    }
    manifest_rows = []
    for stage, frame in artifacts.items():
        path = output_dir / f"{stage}.csv"
        frame.to_csv(path, index=False)
        manifest_rows.append({
            "stage": stage, "path": str(path.relative_to(PROJECT_ROOT)),
            "rows": len(frame), "sha256": _sha256(path),
        })
    summary = {
        "run_id": resolved_run_id,
        "valuation_date": str(market["valuation_date"]),
        "reporting_currency": "INR",
        "synthetic_trade_count": int(load_counts["trades"]),
        "sbm_selected_scenario": sbm["selected_scenario"],
        "sbm_capital_inr": float(sbm["sbm_capital"]),
        "drc_capital_inr": float(drc["drc_capital"]),
        "rrao_capital_inr": float(rrao["rrao_capital"]),
        "frtb_sa_capital_inr": total_capital,
        "market_rwa_inr": market_rwa,
        "rwa_multiplier": 12.5,
    }
    summary_path = output_dir / "16_capital_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest_rows.append({"stage": "capital_summary", "path": str(summary_path.relative_to(PROJECT_ROOT)), "rows": 1, "sha256": _sha256(summary_path)})
    manifest = {"run_id": resolved_run_id, "created_at_utc": datetime.now(timezone.utc).isoformat(), "artifacts": manifest_rows}
    manifest_path = output_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (PROJECT_ROOT / "outputs" / "latest_run.txt").write_text(resolved_run_id + "\n", encoding="utf-8")
    _record_run(resolved_run_id, valuations, manifest_rows)
    return summary


def _price_book(trades: pd.DataFrame, market: Dict) -> pd.DataFrame:
    rows = []
    for trade in trades.to_dict(orient="records"):
        local = price_trade_local(trade, market)
        inr = price_trade_inr(trade, market)
        fx_rate = 1.0 if trade["currency"] == "INR" else float(market["fx"][f"{trade['currency']}INR"])
        rows.append({
            "trade_id": trade["trade_id"], "desk": trade["desk"],
            "sub_portfolio": trade["sub_portfolio"], "instrument_type": trade["instrument_type"],
            "product_form": trade["product_form"], "currency": trade["currency"],
            "market_value_local": local, "fx_to_inr": fx_rate, "market_value_inr": inr,
        })
    return pd.DataFrame(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _record_run(run_id: str, valuations: pd.DataFrame, artifacts: list) -> None:
    config = load_project_config()
    with sqlite3.connect(database_path()) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """INSERT INTO engine_runs(run_id, engine_method, portfolio_id, market_data_set_id,
               parameter_set_id, reporting_currency, completed_at, status)
               VALUES (?, 'SA', ?, 'SYNTHETIC_MARKET_2026_06_30', 'BASEL_FRTB_SA_2026_08_25',
               'INR', CURRENT_TIMESTAMP, 'completed')""",
            (run_id, config["portfolio"]["portfolio_id"]),
        )
        for row in valuations.to_dict(orient="records"):
            connection.execute("UPDATE trades SET market_value = ? WHERE trade_id = ?", (float(row["market_value_inr"]), row["trade_id"]))
        for artifact in artifacts:
            connection.execute(
                "INSERT INTO run_artifacts(run_id, calculation_stage, artifact_path, sha256, row_count) VALUES (?, ?, ?, ?, ?)",
                (run_id, artifact["stage"], artifact["path"], artifact["sha256"], artifact["rows"]),
            )
        connection.commit()
