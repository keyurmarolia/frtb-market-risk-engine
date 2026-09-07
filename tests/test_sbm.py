import math

import pandas as pd

from frtb_engine.config import load_market_data
from frtb_engine.parameters import risk_weight, scenario_correlation
from frtb_engine.sbm import calculate_sbm, net_and_weight
from frtb_engine.sensitivities import calculate_curvature, calculate_delta, calculate_vega, load_trades


def test_basel_girr_weights() -> None:
    base = {"risk_class": "GIRR", "bucket": "INR", "factor_type": "standard"}
    assert risk_weight({**base, "tenor": 0.25}, "DELTA") == 0.017
    assert risk_weight({**base, "tenor": 10.0}, "DELTA") == 0.011


def test_basel_fx_weight() -> None:
    factor = {"risk_class": "FX", "bucket": "USD", "tenor": None, "factor_type": "standard"}
    assert risk_weight(factor, "DELTA") == 0.15


def test_correlation_scenario_transformations() -> None:
    assert scenario_correlation(0.60, "medium") == 0.60
    assert scenario_correlation(0.60, "high") == 0.75
    assert math.isclose(scenario_correlation(0.60, "low"), 0.45)


def test_exact_factor_netting_occurs_before_weighting() -> None:
    detail = pd.DataFrame([
        {"risk_class": "FX", "bucket": "USD", "risk_measure": "DELTA", "risk_factor_id": "USDINR", "tenor": None, "factor_type": "standard", "name": "USDINR", "curve": "fx", "location": "GLOBAL", "raw_sensitivity": 100.0},
        {"risk_class": "FX", "bucket": "USD", "risk_measure": "DELTA", "risk_factor_id": "USDINR", "tenor": None, "factor_type": "standard", "name": "USDINR", "curve": "fx", "location": "GLOBAL", "raw_sensitivity": -40.0},
    ])
    netted = net_and_weight(detail)
    assert len(netted) == 1
    assert netted.iloc[0]["raw_sensitivity"] == 60.0
    assert netted.iloc[0]["weighted_sensitivity"] == 9.0


def test_full_sbm_runs_all_three_scenarios_and_seven_classes() -> None:
    trades = load_trades()
    market = load_market_data()
    delta = calculate_delta(trades, market)
    vega = calculate_vega(trades, market)
    curvature = calculate_curvature(trades, market, delta, risk_weight)
    result = calculate_sbm(delta, vega, curvature)
    assert set(result["scenario_summary"]["scenario"]) == {"low", "medium", "high"}
    assert result["class_results"]["risk_class"].nunique() == 7
    assert result["sbm_capital"] > 0

    girr_delta = result["class_results"].query(
        "risk_class == 'GIRR' and risk_measure == 'DELTA'"
    )["capital"]
    assert girr_delta.notna().all()
    assert (girr_delta > 0).all()

    curvature_capital = result["class_results"].query(
        "risk_measure == 'CURVATURE'"
    )["capital"]
    assert (curvature_capital > 0).any()
