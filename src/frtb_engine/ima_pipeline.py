"""End-to-end IMA orchestration and combined SA/IMA market-risk capital."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import yaml

from frtb_engine.config import PROJECT_ROOT, load_ima_parameters, load_market_data, load_project_config
from frtb_engine.database import database_path, load_synthetic_book
from frtb_engine.drc import calculate_drc
from frtb_engine.ima import (
    backtesting_multiplier,
    build_factor_inventory,
    build_factor_pnl,
    calculate_backtesting,
    calculate_daily_pnl_and_pla,
    calculate_es_and_imcc,
    calculate_ima_drc,
    calculate_nmrf_ses,
    determine_desk_eligibility,
    evaluate_rfet,
    generate_portfolio_history,
    generate_realistic_history,
    generate_rpo_observations,
    liquidity_horizon_es,
)
from frtb_engine.parameters import risk_weight
from frtb_engine.pipeline import _price_book, run_sa
from frtb_engine.rrao import calculate_rrao
from frtb_engine.sbm import calculate_sbm
from frtb_engine.sensitivities import calculate_curvature, calculate_delta, calculate_vega, load_trades
from frtb_engine.validation import validate_foundation


def run_ima(run_id: str | None = None) -> Dict[str, Any]:
    """Run IMA, desk eligibility, SA fallback and final Market RWA."""
    validate_foundation()
    load_synthetic_book()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    resolved_run_id = run_id or f"IMA_{timestamp}"
    output_dir = PROJECT_ROOT / "outputs" / resolved_run_id
    if output_dir.exists():
        raise FileExistsError(f"Run directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    sa_summary = run_sa(run_id=f"SA_{timestamp}")
    trades = load_trades()
    market = load_market_data()
    inventory, exposures = build_factor_inventory(trades, market)
    history = generate_realistic_history(inventory)
    observations = generate_rpo_observations(inventory)
    rfet = evaluate_rfet(inventory, observations)
    factor_pnl = build_factor_pnl(history, exposures, inventory)

    daily_dates = sorted(pd.to_datetime(history["date"].unique()))[-501:]
    portfolio_history = generate_portfolio_history(trades, daily_dates)
    pnl_and_pla = calculate_daily_pnl_and_pla(
        history, exposures, inventory, rfet, portfolio_history, trades, market
    )
    backtesting = calculate_backtesting(pnl_and_pla["daily_pnl"])
    eligibility = determine_desk_eligibility(
        pnl_and_pla["pla"], backtesting["summary"], trades["desk"].unique()
    )
    desk_sa = pd.DataFrame([
        {"desk": desk, **calculate_sa_charge(trades[trades["desk"] == desk].copy(), market)}
        for desk in sorted(trades["desk"].unique())
    ])
    eligible_desks = set(eligibility.loc[eligibility["ima_eligible"], "desk"])
    fallback_desks = set(eligibility.loc[~eligibility["ima_eligible"], "desk"])
    eligible_sa_share = (
        float(desk_sa.loc[desk_sa["desk"].isin(eligible_desks), "sa_capital_inr"].sum())
        / float(desk_sa["sa_capital_inr"].sum())
        if float(desk_sa["sa_capital_inr"].sum()) else 0.0
    )
    if eligible_sa_share < float(load_ima_parameters()["capital"]["minimum_ima_share"]):
        eligibility["final_treatment"] = "SA_FALLBACK"
        eligibility["ima_eligible"] = False
        eligibility["eligibility_reason"] = "Bank-level minimum IMA coverage share was not met"
        eligible_desks = set()
        fallback_desks = set(trades["desk"].unique())

    eligible_factor_pnl = factor_pnl[factor_pnl["desk"].isin(eligible_desks)].copy()
    eligible_factors = set(eligible_factor_pnl["risk_factor_id"])
    eligible_inventory = inventory[inventory["risk_factor_id"].isin(eligible_factors)].copy()
    eligible_rfet = rfet[rfet["risk_factor_id"].isin(eligible_factors)].copy()
    es = calculate_es_and_imcc(eligible_factor_pnl, eligible_inventory, eligible_rfet)
    nmrf = calculate_nmrf_ses(eligible_factor_pnl, eligible_inventory, eligible_rfet)
    eligible_trades = trades[trades["desk"].isin(eligible_desks)].copy()
    ima_drc = calculate_ima_drc(eligible_trades, market, portfolio_history)

    multiplier_detail = _bankwide_backtesting(pnl_and_pla["daily_pnl"], eligible_desks)
    multiplier = backtesting_multiplier(int(multiplier_detail["exceptions_used"]))
    capital_history = _capital_history(
        eligible_factor_pnl, eligible_inventory, eligible_rfet, es, float(nmrf["ses_inr"])
    )
    average_imcc = float(capital_history.tail(60)["imcc_inr"].mean())
    average_ses = float(capital_history.tail(60)["ses_inr"].mean())
    current_non_drc = float(es["imcc_inr"] + nmrf["ses_inr"])
    average_non_drc = float(multiplier * average_imcc + average_ses)
    non_drc_capital = max(current_non_drc, average_non_drc)

    fallback_trades = trades[trades["desk"].isin(fallback_desks)].copy()
    sa_fallback = calculate_sa_charge(fallback_trades, market)
    sa_eligible = calculate_sa_charge(eligible_trades, market)
    amber_desks = set(eligibility.loc[eligibility["final_treatment"] == "IMA_AMBER", "desk"])
    sa_amber = float(desk_sa.loc[desk_sa["desk"].isin(amber_desks), "sa_capital_inr"].sum())
    eligible_ima_before_surcharge = non_drc_capital + float(ima_drc["ima_drc_capital_inr"])
    amber_share, amber_surcharge = calculate_amber_surcharge(
        sa_amber, float(sa_eligible["sa_capital_inr"]), eligible_ima_before_surcharge
    )
    total_capital = eligible_ima_before_surcharge + amber_surcharge + float(sa_fallback["sa_capital_inr"])
    market_rwa = total_capital * float(load_ima_parameters()["capital"]["market_rwa_multiplier"])

    desk_summary = eligibility.merge(desk_sa, on="desk", how="left")
    desk_summary["ima_component_inr"] = 0.0
    desk_summary["amber_surcharge_inr"] = 0.0
    desk_summary["sa_fallback_component_inr"] = 0.0
    eligible_weights = desk_summary.loc[desk_summary["ima_eligible"], "sa_capital_inr"]
    weight_total = float(eligible_weights.sum())
    if weight_total:
        desk_summary.loc[desk_summary["ima_eligible"], "ima_component_inr"] = (
            desk_summary.loc[desk_summary["ima_eligible"], "sa_capital_inr"] / weight_total * eligible_ima_before_surcharge
        )
    amber_weight_total = float(desk_summary.loc[desk_summary["final_treatment"] == "IMA_AMBER", "sa_capital_inr"].sum())
    if amber_weight_total:
        mask = desk_summary["final_treatment"] == "IMA_AMBER"
        desk_summary.loc[mask, "amber_surcharge_inr"] = (
            desk_summary.loc[mask, "sa_capital_inr"] / amber_weight_total * amber_surcharge
        )
    fallback_weight_total = float(desk_summary.loc[~desk_summary["ima_eligible"], "sa_capital_inr"].sum())
    if fallback_weight_total:
        mask = ~desk_summary["ima_eligible"]
        desk_summary.loc[mask, "sa_fallback_component_inr"] = (
            desk_summary.loc[mask, "sa_capital_inr"] / fallback_weight_total * float(sa_fallback["sa_capital_inr"])
        )
    desk_summary["final_capital_treatment_inr"] = (
        desk_summary["ima_component_inr"]
        + desk_summary["amber_surcharge_inr"]
        + desk_summary["sa_fallback_component_inr"]
    )

    summary = {
        "run_id": resolved_run_id,
        "sa_run_id": sa_summary["run_id"],
        "valuation_date": str(market["valuation_date"]),
        "reporting_currency": "INR",
        "data_classification": "synthetic_regime_aware_with_regulatory_parameters_separate",
        "full_book_sa_capital_inr": float(sa_summary["frtb_sa_capital_inr"]),
        "eligible_desk_count": len(eligible_desks),
        "fallback_desk_count": len(fallback_desks),
        "eligible_desks": sorted(eligible_desks),
        "fallback_desks": sorted(fallback_desks),
        "eligible_sa_share": eligible_sa_share,
        "imcc_current_inr": float(es["imcc_inr"]),
        "imcc_average_60_day_inr": average_imcc,
        "ses_current_inr": float(nmrf["ses_inr"]),
        "ses_average_60_day_inr": average_ses,
        "backtesting_multiplier": multiplier,
        "ima_non_drc_capital_inr": non_drc_capital,
        "ima_drc_current_inr": float(ima_drc["current_drc_inr"]),
        "ima_drc_average_12_week_inr": float(ima_drc["average_12_week_drc_inr"]),
        "ima_drc_capital_inr": float(ima_drc["ima_drc_capital_inr"]),
        "ima_eligible_capital_before_surcharge_inr": eligible_ima_before_surcharge,
        "pla_amber_surcharge_inr": amber_surcharge,
        "sa_fallback_capital_inr": float(sa_fallback["sa_capital_inr"]),
        "final_frtb_market_risk_capital_inr": total_capital,
        "market_rwa_inr": market_rwa,
        "rwa_multiplier": 12.5,
        "standalone_market_risk_floor_applied": False,
        "aggregation_note": "MAR33 aggregation is applied; full-book SA is retained for comparison and wider Basel output-floor use",
        "stress_window_start": str(pd.Timestamp(es["stress_start"]).date()),
        "stress_window_end": str(pd.Timestamp(es["stress_end"]).date()),
    }

    artifacts: dict[str, pd.DataFrame] = {
        "01_ima_factor_inventory": inventory,
        "02_synthetic_rpo_observations": observations,
        "03_rfet_results": rfet,
        "04_synthetic_factor_history": history,
        "05_factor_exposures": exposures,
        "06_daily_factor_pnl": factor_pnl,
        "07_reduced_factor_selection": es["reduced_selection"],
        "08_stress_window_scan": es["stress_scan"],
        "09_es_summary": es["es_summary"],
        "10_liquidity_horizon_es_components": es["lh_components"],
        "11_scaled_es_and_imcc": es["scaled_es"],
        "12_nmrf_ses_detail": nmrf["detail"],
        "13_nmrf_ses_summary": nmrf["summary"],
        "14_ima_drc_issuer_inputs": ima_drc["issuer_inputs"],
        "15_ima_drc_loss_distribution": ima_drc["loss_distribution"],
        "16_ima_drc_tail_trace": ima_drc["tail_trace"],
        "17_ima_drc_weekly_history": ima_drc["weekly_history"],
        "18_portfolio_snapshots": portfolio_history,
        "19_daily_hpl_rtpl_apl": pnl_and_pla["daily_pnl"],
        "19a_trade_hpl_rtpl_apl_detail": pnl_and_pla["trade_pnl_detail"],
        "20_pla_results": pnl_and_pla["pla"],
        "21_backtesting_detail": backtesting["detail"],
        "22_backtesting_summary": backtesting["summary"],
        "23_desk_eligibility": eligibility,
        "24_ima_capital_history": capital_history,
        "25_desk_capital_summary": desk_summary,
        "26_bankwide_backtesting": pd.DataFrame([multiplier_detail | {"multiplier": multiplier}]),
    }
    manifest_rows = []
    for stage, frame in artifacts.items():
        path = _write_frame(output_dir, stage, frame)
        manifest_rows.append(_manifest_row(stage, path, len(frame)))
    summary_path = output_dir / "27_combined_capital_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest_rows.append(_manifest_row("combined_capital_summary", summary_path, 1))
    manifest = {
        "run_id": resolved_run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_note": "Synthetic inputs and Basel regulatory parameters are separately labelled in every retained stage",
        "artifacts": manifest_rows,
    }
    manifest_path = output_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (PROJECT_ROOT / "outputs" / "latest_ima_run.txt").write_text(resolved_run_id + "\n", encoding="utf-8")
    _save_canonical_inputs(inventory, history, observations, portfolio_history)
    _record_ima_run(resolved_run_id, manifest_rows, artifacts, summary)
    return summary


def calculate_sa_charge(trades: pd.DataFrame, market: Dict[str, Any]) -> Dict[str, float | str]:
    if trades.empty:
        return {"sbm_capital_inr": 0.0, "sa_drc_capital_inr": 0.0, "rrao_capital_inr": 0.0, "sa_capital_inr": 0.0, "selected_scenario": "not_applicable"}
    valuations = _price_book(trades, market)
    delta = calculate_delta(trades, market)
    vega = calculate_vega(trades, market)
    if delta.empty:
        sbm = {"sbm_capital": 0.0, "selected_scenario": "not_applicable"}
    else:
        curvature = calculate_curvature(trades, market, delta, risk_weight)
        sbm = calculate_sbm(delta, vega, curvature)
    drc = calculate_drc(trades, valuations, market)
    rrao = calculate_rrao(trades, market)
    total = float(sbm["sbm_capital"] + drc["drc_capital"] + rrao["rrao_capital"])
    return {
        "sbm_capital_inr": float(sbm["sbm_capital"]),
        "sa_drc_capital_inr": float(drc["drc_capital"]),
        "rrao_capital_inr": float(rrao["rrao_capital"]),
        "sa_capital_inr": total,
        "selected_scenario": str(sbm["selected_scenario"]),
    }


def calculate_amber_surcharge(
    standalone_amber_sa: float,
    standalone_green_and_amber_sa: float,
    eligible_ima_capital: float,
) -> tuple[float, float]:
    """Return the MAR33.45 coefficient and positive amber-desk surcharge."""
    if standalone_green_and_amber_sa <= 0:
        return 0.0, 0.0
    coefficient = 0.5 * standalone_amber_sa / standalone_green_and_amber_sa
    surcharge = coefficient * max(standalone_green_and_amber_sa - eligible_ima_capital, 0.0)
    return float(coefficient), float(surcharge)


def _bankwide_backtesting(daily_pnl: pd.DataFrame, eligible_desks: set[str]) -> Dict[str, Any]:
    eligible = daily_pnl[daily_pnl["desk"].isin(eligible_desks)].copy()
    grouped = eligible.groupby("date", as_index=False)[["hpl_inr", "apl_inr"]].sum().sort_values("date")
    outcomes = []
    for index in range(250, len(grouped)):
        history = grouped.iloc[index - 250:index]
        outcome = grouped.iloc[index]
        var_99 = max(float(-history["hpl_inr"].quantile(0.01)), 0.0)
        outcomes.append((var_99, float(outcome["hpl_inr"]), float(outcome["apl_inr"])))
    hpl = sum(-hpl_value > var for var, hpl_value, _ in outcomes)
    apl = sum(-apl_value > var for var, _, apl_value in outcomes)
    used = max(hpl, apl)
    return {
        "observations": len(outcomes), "hpl_exceptions_99": hpl,
        "apl_exceptions_99": apl, "exceptions_used": used,
        "exception_rule": "Maximum of bank-wide HPL and APL exceptions",
    }


def _capital_history(
    factor_pnl: pd.DataFrame,
    inventory: pd.DataFrame,
    rfet: pd.DataFrame,
    es_result: Dict[str, Any],
    ses: float,
) -> pd.DataFrame:
    """Recalculate 60 dated ES measures; hold the calibrated stress set fixed."""
    params = load_ima_parameters()["expected_shortfall"]
    confidence = float(params["confidence_level"])
    dates = pd.DatetimeIndex(sorted(pd.to_datetime(factor_pnl["date"].unique())))
    calculation_dates = dates[-60:]
    mrf = set(rfet.loc[rfet["modellability_status"] == "MRF", "risk_factor_id"])
    reduced = set(es_result["reduced_selection"].loc[
        es_result["reduced_selection"]["included_in_reduced_set"], "risk_factor_id"
    ])
    factor_class = inventory.set_index("risk_factor_id")["broad_risk_class"].to_dict()
    scopes = {"ALL": mrf}
    for risk_class in params["broad_risk_classes"]:
        scopes[risk_class] = {factor for factor in mrf if factor_class.get(factor) == risk_class}
    stress_reduced = es_result["es_summary"].query(
        "period == 'STRESS' and factor_set == 'REDUCED'"
    ).set_index("scope")["liquidity_horizon_adjusted_es_inr"].to_dict()
    rows = []
    for date in calculation_dates:
        available_dates = dates[dates <= date]
        current_dates = available_dates[-int(params["current_window_business_days"]):]
        current = factor_pnl[factor_pnl["date"].isin(current_dates)]
        scaled_by_scope = {}
        for scope, full_factors in scopes.items():
            full = liquidity_horizon_es(current, inventory, full_factors, confidence).liquidity_horizon_adjusted_es
            reduced_current = liquidity_horizon_es(
                current, inventory, full_factors & reduced, confidence
            ).liquidity_horizon_adjusted_es
            ratio = max(full / reduced_current, float(params["stress_scaling_ratio_floor"])) if reduced_current else 1.0
            scaled_by_scope[scope] = float(stress_reduced.get(scope, 0.0)) * ratio
        imcc = (
            float(params["imcc_unconstrained_weight"]) * scaled_by_scope["ALL"]
            + float(params["imcc_constrained_weight"])
            * sum(value for scope, value in scaled_by_scope.items() if scope != "ALL")
        )
        rows.append({
            "date": date, "imcc_inr": imcc, "ses_inr": ses,
            "history_basis": "Dated 250-day ES recalculation with the current calibrated stress period and current NMRF stress scenarios",
        })
    return pd.DataFrame(rows)


def _write_frame(output_dir: Path, stage: str, frame: pd.DataFrame) -> Path:
    if len(frame) > 20_000:
        path = output_dir / f"{stage}.csv.gz"
        frame.to_csv(path, index=False, compression="gzip")
    else:
        path = output_dir / f"{stage}.csv"
        frame.to_csv(path, index=False)
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_row(stage: str, path: Path, rows: int) -> dict[str, Any]:
    return {"stage": stage, "path": str(path.relative_to(PROJECT_ROOT)), "rows": rows, "sha256": _sha256(path)}


def _save_canonical_inputs(
    inventory: pd.DataFrame,
    history: pd.DataFrame,
    observations: pd.DataFrame,
    portfolio_history: pd.DataFrame,
) -> None:
    target = PROJECT_ROOT / "data" / "synthetic" / "ima"
    target.mkdir(parents=True, exist_ok=True)
    inventory.to_csv(target / "risk_factor_inventory.csv", index=False)
    history.to_csv(target / "risk_factor_history.csv.gz", index=False, compression="gzip")
    observations.to_csv(target / "rfet_observations.csv", index=False)
    portfolio_history.to_csv(target / "daily_portfolio_snapshots.csv.gz", index=False, compression="gzip")
    manifest = {
        "data_classification": "synthetic",
        "construction": "correlated economic factors, volatility clustering, named stress regimes and fixed random seeds",
        "not_real_price_warning": "RFET observations are synthetic transaction and committed-quote events, not public closing prices",
        "valuation_anchor": "data/synthetic/market_data.yaml",
        "files": {
            "risk_factor_inventory.csv": "factor definitions, liquidity horizons and data labels",
            "risk_factor_history.csv.gz": "ten-year joint factor history",
            "rfet_observations.csv": "synthetic qualifying-observation evidence",
            "daily_portfolio_snapshots.csv.gz": "501 dated position snapshots supporting 500 next-day P&L outcomes",
        },
    }
    (target / "data_manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def _record_ima_run(
    run_id: str,
    manifest_rows: list[dict[str, Any]],
    artifacts: dict[str, pd.DataFrame],
    summary: dict[str, Any],
) -> None:
    config = load_project_config()
    with sqlite3.connect(database_path()) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """INSERT OR REPLACE INTO regulatory_parameter_sets(
               parameter_set_id, framework, snapshot_date, effective_date, basis,
               source_manifest_path, status) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("BASEL_FRTB_IMA_2026_08_25", "Basel Framework", "2026-08-25", "2023-01-01",
             "Basel global minimum standard", config["provenance"]["regulatory_manifest"],
             "educational_parameter_set_loaded_and_validated"),
        )
        connection.execute(
            """INSERT INTO engine_runs(run_id, engine_method, portfolio_id, market_data_set_id,
               parameter_set_id, reporting_currency, completed_at, status)
               VALUES (?, 'IMA', ?, 'SYNTHETIC_MARKET_2026_06_30', 'BASEL_FRTB_IMA_2026_08_25',
               'INR', CURRENT_TIMESTAMP, 'completed')""",
            (run_id, config["portfolio"]["portfolio_id"]),
        )
        for artifact in manifest_rows:
            connection.execute(
                "INSERT INTO run_artifacts(run_id, calculation_stage, artifact_path, sha256, row_count) VALUES (?, ?, ?, ?, ?)",
                (run_id, artifact["stage"], artifact["path"], artifact["sha256"], artifact["rows"]),
            )
        connection.commit()
        table_map = {
            "ima_factor_inventory": artifacts["01_ima_factor_inventory"],
            "ima_rfet_results": artifacts["03_rfet_results"],
            "ima_es_summary": artifacts["09_es_summary"],
            "ima_nmrf_ses": artifacts["12_nmrf_ses_detail"],
            "ima_desk_eligibility": artifacts["23_desk_eligibility"],
            "ima_desk_capital": artifacts["25_desk_capital_summary"],
            "ima_capital_summary": pd.DataFrame([{
                key: json.dumps(value) if isinstance(value, (list, dict)) else value
                for key, value in summary.items()
            }]),
        }
        for table, frame in table_map.items():
            frame.to_sql(table, connection, if_exists="replace", index=False)
