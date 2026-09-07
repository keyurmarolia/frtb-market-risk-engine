import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from frtb_engine.config import load_ima_parameters
from frtb_engine.database import database_path
from frtb_engine.ima import expected_shortfall
from frtb_engine.ima_pipeline import calculate_amber_surcharge


ROOT = Path(__file__).resolve().parents[1]


def latest_ima_run() -> Path:
    run_id = (ROOT / "outputs/latest_ima_run.txt").read_text(encoding="utf-8").strip()
    return ROOT / "outputs" / run_id


def test_ima_parameters_hold_current_basel_controls() -> None:
    params = load_ima_parameters()
    assert params["rfet"]["route_1_minimum_observations"] == 24
    assert params["rfet"]["route_2_minimum_observations"] == 100
    assert params["expected_shortfall"]["confidence_level"] == 0.975
    assert params["expected_shortfall"]["liquidity_horizons_days"] == [10, 20, 40, 60, 120]
    assert params["expected_shortfall"]["reduced_set_minimum_coverage"] == 0.75
    assert params["ima_drc"]["confidence_level"] == 0.999
    assert params["ima_drc"]["probability_of_default_floor"] == 0.0003
    assert params["ima_drc"]["systematic_factor_types"] == ["GLOBAL", "SECTOR_REGION"]


def test_expected_shortfall_is_average_beyond_the_quantile() -> None:
    pnl = np.array([10.0, 5.0, 0.0, -5.0, -10.0, -20.0, -30.0, -40.0])
    result = expected_shortfall(pnl, confidence=0.75)
    losses = -pnl
    threshold = np.quantile(losses, 0.75)
    assert result == losses[losses >= threshold].mean()


def test_rfet_produces_mrf_and_nmrf_with_explanations() -> None:
    rfet = pd.read_csv(latest_ima_run() / "03_rfet_results.csv")
    assert set(rfet["modellability_status"]) == {"MRF", "NMRF"}
    assert rfet["rfet_reason"].str.len().gt(20).all()
    assert set(rfet["evidence_data_status"]) == {"SYNTHETIC_RFET_EVIDENCE"}
    assert (rfet.loc[rfet["rfet_route"] == "100_OBSERVATION_ROUTE", "qualifying_observation_count"] >= 100).all()


def test_all_five_liquidity_horizons_are_used() -> None:
    factors = pd.read_csv(latest_ima_run() / "01_ima_factor_inventory.csv")
    assert set(factors["liquidity_horizon_days"]) == {10, 20, 40, 60, 120}
    assert set(factors["input_data_status"]) == {"SYNTHETIC_MARKET_HISTORY"}


def test_reduced_set_coverage_and_imcc_components() -> None:
    scaled = pd.read_csv(latest_ima_run() / "11_scaled_es_and_imcc.csv")
    assert scaled["coverage_pass"].all()
    assert (scaled["stress_scaling_ratio"] >= 1.0).all()
    unconstrained = scaled.loc[scaled["scope"] == "ALL", "scaled_es_capital_inr"].iloc[0]
    constrained = scaled.loc[scaled["scope"] != "ALL", "scaled_es_capital_inr"].sum()
    summary = json.loads((latest_ima_run() / "27_combined_capital_summary.json").read_text())
    assert np.isclose(summary["imcc_current_inr"], 0.5 * unconstrained + 0.5 * constrained)


def test_pla_and_eligibility_use_valid_zones_and_cover_every_desk() -> None:
    pla = pd.read_csv(latest_ima_run() / "20_pla_results.csv")
    eligibility = pd.read_csv(latest_ima_run() / "23_desk_eligibility.csv", keep_default_na=False)
    assert set(pla["pla_zone"]).issubset({"GREEN", "AMBER", "RED"})
    assert set(eligibility["desk"]) == {"Rates", "Credit", "Equity", "FX", "Commodity", "Residual Risk"}
    assert not eligibility.astype(str).apply(lambda column: column.str.contains(r"\bNaN\b", case=False, regex=True)).any().any()
    assert set(eligibility["final_treatment"]).issubset({"IMA_GREEN", "IMA_AMBER", "SA_FALLBACK"})
    assert set(eligibility.loc[eligibility["desk"] == "Residual Risk", "final_treatment"]) == {"SA_FALLBACK"}


def test_backtesting_has_no_look_ahead_and_uses_250_outcomes() -> None:
    detail = pd.read_csv(latest_ima_run() / "21_backtesting_detail.csv")
    summary = pd.read_csv(latest_ima_run() / "22_backtesting_summary.csv")
    assert (pd.to_datetime(detail["forecast_date"]) < pd.to_datetime(detail["outcome_date"])).all()
    assert set(summary["observations"]) == {250}
    assert set(detail["forecast_information"]) == {"Only the preceding 250 observations"}


def test_ima_drc_is_reproducible_and_tail_is_traceable() -> None:
    issuers = pd.read_csv(latest_ima_run() / "14_ima_drc_issuer_inputs.csv")
    trace = pd.read_csv(latest_ima_run() / "16_ima_drc_tail_trace.csv")
    summary = json.loads((latest_ima_run() / "27_combined_capital_summary.json").read_text())
    assert (issuers["pd"] >= 0.0003).all()
    assert {"global_loading", "sector_region_loading", "idiosyncratic_loading"}.issubset(issuers.columns)
    assert not trace.empty
    assert summary["ima_drc_capital_inr"] == max(
        summary["ima_drc_current_inr"], summary["ima_drc_average_12_week_inr"]
    )


def test_combined_capital_uses_ima_plus_amber_surcharge_plus_sa_fallback() -> None:
    summary = json.loads((latest_ima_run() / "27_combined_capital_summary.json").read_text())
    expected = (
        summary["ima_eligible_capital_before_surcharge_inr"]
        + summary["pla_amber_surcharge_inr"]
        + summary["sa_fallback_capital_inr"]
    )
    assert np.isclose(summary["final_frtb_market_risk_capital_inr"], expected)
    assert summary["market_rwa_inr"] == summary["final_frtb_market_risk_capital_inr"] * 12.5
    assert summary["standalone_market_risk_floor_applied"] is False


def test_amber_surcharge_uses_one_half_weight_and_positive_difference() -> None:
    coefficient, surcharge = calculate_amber_surcharge(30.0, 100.0, 80.0)
    assert coefficient == 0.15
    assert surcharge == 3.0
    assert calculate_amber_surcharge(30.0, 100.0, 120.0)[1] == 0.0


def test_ima_tables_are_retained_in_shared_database() -> None:
    required = {
        "ima_factor_inventory", "ima_rfet_results", "ima_es_summary",
        "ima_nmrf_ses", "ima_desk_eligibility", "ima_desk_capital", "ima_capital_summary",
    }
    with sqlite3.connect(database_path()) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        completed = connection.execute("SELECT COUNT(*) FROM engine_runs WHERE engine_method='IMA' AND status='completed'").fetchone()[0]
    assert required.issubset(tables)
    assert completed >= 1
