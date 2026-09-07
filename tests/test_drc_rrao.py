import pandas as pd

from frtb_engine.config import load_market_data
from frtb_engine.drc import calculate_drc
from frtb_engine.pricing import price_trade_inr
from frtb_engine.rrao import calculate_rrao
from frtb_engine.sensitivities import load_trades


def valuation_frame(trades: pd.DataFrame) -> pd.DataFrame:
    market = load_market_data()
    return pd.DataFrame([
        {"trade_id": row["trade_id"], "market_value_inr": price_trade_inr(row, market)}
        for row in trades.to_dict(orient="records")
    ])


def test_three_drc_classes_are_separate() -> None:
    trades = load_trades()
    result = calculate_drc(trades, valuation_frame(trades))
    classes = set(result["summary"]["drc_class"])
    assert {"NON_SECURITISATION", "SECURITISATION_NON_CTP", "SECURITISATION_CTP"}.issubset(classes)


def test_same_obligor_default_hedge_is_netted() -> None:
    trades = load_trades()
    result = calculate_drc(trades, valuation_frame(trades))
    gross = result["gross_jtd"]
    net = result["net_jtd"]
    axis_gross = gross[gross["obligor"] == "AXIS_BANK"]["gross_jtd"].sum()
    axis_net = net[net["obligor"] == "AXIS_BANK"]["net_jtd"].sum()
    assert axis_net == axis_gross
    assert abs(axis_net) < gross[gross["obligor"] == "AXIS_BANK"]["gross_jtd"].abs().sum()


def test_drc_total_is_sum_of_three_categories() -> None:
    trades = load_trades()
    result = calculate_drc(trades, valuation_frame(trades))
    detail = result["summary"]
    parts = detail[detail["drc_class"] != "TOTAL_DRC"]["capital"].sum()
    assert result["drc_capital"] == parts


def test_rrao_uses_gross_notional_and_both_weights() -> None:
    trades = load_trades()
    result = calculate_rrao(trades)
    detail = result["detail"]
    assert set(detail["rrao_type"]) == {"EXOTIC_UNDERLYING", "OTHER_RESIDUAL_RISK"}
    assert set(detail["risk_weight"]) == {0.01, 0.001}
    assert (detail["rrao_charge"] == detail["gross_notional_inr"] * detail["risk_weight"]).all()
    assert not detail["netting_allowed"].any()
