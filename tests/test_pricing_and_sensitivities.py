import math

import pandas as pd

from frtb_engine.config import load_market_data
from frtb_engine.parameters import risk_weight, within_bucket_correlation
from frtb_engine.pricing import black_scholes, price_trade_inr, up_and_out_call
from frtb_engine.sensitivities import calculate_delta, calculate_vega, load_trades


def test_put_call_parity() -> None:
    spot, strike, maturity, rate, vol = 100.0, 100.0, 1.0, 0.05, 0.20
    call = black_scholes(spot, strike, maturity, rate, vol, "CALL")
    put = black_scholes(spot, strike, maturity, rate, vol, "PUT")
    assert math.isclose(call - put, spot - strike * math.exp(-rate * maturity), rel_tol=1e-10)


def test_all_trades_price_in_inr() -> None:
    trades = load_trades()
    market = load_market_data()
    values = [price_trade_inr(row, market) for row in trades.to_dict(orient="records")]
    assert len(values) == 48
    assert all(math.isfinite(value) for value in values)


def test_foreign_bond_generates_girr_and_fx_delta() -> None:
    trades = load_trades()
    market = load_market_data()
    delta = calculate_delta(trades[trades["trade_id"] == "R04"], market)
    assert set(delta["risk_class"]) == {"GIRR", "FX"}


def test_option_generates_delta_and_vega() -> None:
    trades = load_trades()
    market = load_market_data()
    option = trades[trades["trade_id"] == "E03"]
    delta = calculate_delta(option, market)
    vega = calculate_vega(option, market)
    assert set(delta["risk_class"]) == {"EQUITY", "GIRR"}
    assert len(vega) == 1
    assert vega.iloc[0]["raw_sensitivity"] > 0


def test_option_rate_dependency_changes_its_value() -> None:
    trades = load_trades()
    market = load_market_data()
    option = trades[trades["trade_id"] == "E03"]
    delta = calculate_delta(option, market)
    assert delta.loc[delta["risk_class"] == "GIRR", "raw_sensitivity"].abs().sum() > 0


def test_vega_is_price_vega_times_current_implied_volatility() -> None:
    trades = load_trades()
    market = load_market_data()
    vega = calculate_vega(trades[trades["trade_id"] == "E03"], market)
    assert math.isclose(
        vega["raw_sensitivity"].sum(),
        (vega["price_vega"] * vega["implied_volatility"]).sum(),
        rel_tol=1e-12,
    )


def test_upper_barrier_call_is_bounded_by_vanilla_call() -> None:
    barrier = up_and_out_call(100.0, 90.0, 130.0, 1.0, 0.05, 0.20)
    vanilla = black_scholes(100.0, 90.0, 1.0, 0.05, 0.20, "CALL")
    assert 0.0 <= barrier <= vanilla


def test_same_underlying_positions_have_same_exact_factor_key() -> None:
    trades = load_trades()
    market = load_market_data()
    subset = trades[trades["trade_id"].isin(["E01", "E02", "E03"])]
    delta = calculate_delta(subset, market)
    equity = delta[delta["risk_class"] == "EQUITY"]
    assert equity["risk_factor_id"].nunique() == 1
    assert equity["risk_factor_id"].iloc[0] == "RELIANCE"


def test_xccy_swap_maps_both_rate_curves_and_flat_basis_factor() -> None:
    trades = load_trades()
    market = load_market_data()
    delta = calculate_delta(trades[trades["trade_id"] == "R12"], market)
    girr = delta[delta["risk_class"] == "GIRR"]
    assert {"USD_OIS_5.0Y", "INR_OIS_5.0Y", "INR_OVER_USD_BASIS"}.issubset(set(girr["risk_factor_id"]))
    basis = girr[girr["factor_type"] == "cross_currency_basis"].iloc[0]
    assert basis["bucket"] == "INR"
    assert pd.isna(basis["tenor"])
    assert risk_weight(basis.to_dict(), "DELTA") == 0.016


def test_special_girr_correlations_follow_flat_factor_rules() -> None:
    yield_factor = {"risk_class": "GIRR", "risk_factor_id": "INR_OIS_5Y", "factor_type": "standard", "tenor": 5.0, "curve": "rates"}
    inflation = {"risk_class": "GIRR", "risk_factor_id": "INR_INFLATION", "factor_type": "inflation", "tenor": None, "curve": "inflation"}
    basis = {"risk_class": "GIRR", "risk_factor_id": "INR_OVER_USD_BASIS", "factor_type": "cross_currency_basis", "tenor": None, "curve": "cross_currency_basis"}
    assert within_bucket_correlation(inflation, yield_factor, "medium") == 0.40
    assert within_bucket_correlation(basis, yield_factor, "medium") == 0.0
    assert within_bucket_correlation(basis, inflation, "medium") == 0.0


def test_foreign_positions_share_the_same_fx_factor_identity() -> None:
    trades = load_trades()
    market = load_market_data()
    delta = calculate_delta(trades[trades["trade_id"].isin(["R04", "C02", "R12"])], market)
    usd_fx = delta[(delta["risk_class"] == "FX") & (delta["risk_factor_id"] == "USDINR")]
    assert len(usd_fx) == 3
    assert usd_fx["name"].nunique() == 1
    assert usd_fx["name"].iloc[0] == "USDINR"
