"""Trade-level FRTB risk-factor mapping and repricing sensitivities."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

import pandas as pd

from frtb_engine.pricing import bumped_market, price_trade_inr


GIRR_TENORS = [0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0]
CSR_TENORS = [0.5, 1.0, 3.0, 5.0, 10.0]
OPTIONAL_INSTRUMENTS = {
    "SWAPTION", "CREDIT_OPTION", "CALLABLE_BOND", "EQUITY_OPTION",
    "BARRIER_OPTION", "FX_OPTION", "DIGITAL_OPTION", "COMMODITY_OPTION",
}


def nearest(value: float, grid: Iterable[float]) -> float:
    return min(grid, key=lambda point: abs(point - value))


def tenor_weights(value: float, grid: Iterable[float]) -> list[tuple[float, float]]:
    points = sorted(float(t) for t in grid)
    if value <= points[0]:
        return [(points[0], 1.0)]
    if value >= points[-1]:
        return [(points[-1], 1.0)]
    for left, right in zip(points, points[1:]):
        if left <= value <= right:
            weight = (value - left) / (right - left)
            return [(t, w) for t, w in [(left, 1 - weight), (right, weight)] if w > 0]
    raise ValueError("Invalid tenor")


def load_trades() -> pd.DataFrame:
    numeric = [
        "quantity", "notional", "maturity_years", "option_expiry_years", "strike",
        "coupon", "fixed_rate", "csr_bucket", "equity_bucket", "commodity_bucket",
        "attachment", "detachment", "is_synthetic",
    ]
    from frtb_engine.config import PROJECT_ROOT
    frame = pd.read_csv(PROJECT_ROOT / "data/synthetic/trades.csv", keep_default_na=False)
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column])
    return frame


def risk_factors_for_trade(trade: Dict[str, Any]) -> List[Dict[str, Any]]:
    factors: List[Dict[str, Any]] = []
    kind = trade["instrument_type"]
    maturity = max(float(trade["maturity_years"]), float(trade["option_expiry_years"]), 0.25)
    currency = trade["currency"]

    rate_sensitive = kind in {
        "BOND", "CORPORATE_BOND", "INFLATION_BOND", "IRS", "FRA", "SWAPTION",
        "XCCY_BASIS_SWAP", "CDS", "CREDIT_OPTION", "CALLABLE_BOND",
        "SECURITISATION_TRANCHE", "CTP_TRANCHE", "CTP_INDEX_HEDGE",
        "EQUITY_FUTURE", "EQUITY_OPTION", "BARRIER_OPTION", "FX_FORWARD",
        "FX_OPTION", "DIGITAL_OPTION", "COMMODITY_OPTION",
    }
    if rate_sensitive:
        for tenor, _ in tenor_weights(maturity, GIRR_TENORS):
            factors.append(_factor("GIRR", currency, f"{currency}_OIS_{tenor}Y", "rates", currency, tenor, False, trade))
    if kind in {"FX_FORWARD", "FX_OPTION", "DIGITAL_OPTION"}:
        foreign = trade["underlying"][:3]
        for tenor, _ in tenor_weights(maturity, GIRR_TENORS):
            factors.append(_factor("GIRR", foreign, f"{foreign}_OIS_{tenor}Y", "rates", foreign, tenor, False, trade))
    if kind == "INFLATION_BOND":
        factors.append(_factor("GIRR", currency, f"{currency}_INFLATION", "inflation", currency, None, False, trade, factor_type="inflation"))
    if kind == "XCCY_BASIS_SWAP":
        pair = trade["underlying"].replace("_BASIS", "")
        first_currency, second_currency = pair[:3], pair[3:6]
        other_currency = second_currency if first_currency == currency else first_currency
        for tenor, _ in tenor_weights(maturity, GIRR_TENORS):
            factors.append(_factor(
                "GIRR", other_currency, f"{other_currency}_OIS_{tenor}Y",
                "rates", other_currency, tenor, False, trade,
            ))
        anchor = "USD" if "USD" in {first_currency, second_currency} else "EUR"
        basis_currency = other_currency if other_currency != anchor else currency
        basis_id = f"{basis_currency}_OVER_{anchor}_BASIS"
        basis_factor = _factor(
            "GIRR", basis_currency, basis_id, "cross_currency_basis",
            trade["underlying"], None, False, trade,
            factor_type="cross_currency_basis",
        )
        basis_factor["name"] = basis_id
        factors.append(basis_factor)

    if trade["csr_class"] != "NONE":
        for tenor, _ in tenor_weights(maturity, CSR_TENORS):
            factors.append(_factor(trade["csr_class"], str(int(trade["csr_bucket"])), f"{trade['underlying']}_{tenor}Y", "credit_spreads", trade["underlying"], tenor, False, trade))

    if kind in {"EQUITY_CASH", "EQUITY_FUTURE", "EQUITY_OPTION", "BARRIER_OPTION"}:
        factors.append(_factor("EQUITY", str(int(trade["equity_bucket"])), trade["underlying"], "equity_spot", trade["underlying"], None, True, trade))
    if kind in {"COMMODITY_FUTURE", "COMMODITY_OPTION"}:
        tenor = nearest(maturity, GIRR_TENORS)
        factor_id = f"{trade['underlying']}_{tenor}Y_GLOBAL"
        factors.append(_factor("COMMODITY", str(int(trade["commodity_bucket"])), factor_id, "commodity_spot", trade["underlying"], tenor, True, trade))
    if kind in {"FX_FORWARD", "FX_OPTION", "DIGITAL_OPTION"}:
        foreign_currency = trade["underlying"][:3]
        factors.append(_factor("FX", foreign_currency, trade["underlying"], "fx", trade["underlying"], None, True, trade))
    elif currency != "INR":
        pair = f"{currency}INR"
        factors.append(_factor("FX", currency, pair, "fx", pair, None, True, trade))
    return factors


def _factor(risk_class: str, bucket: str, factor_id: str, group: str, key: str, tenor: float | None, relative: bool, trade: Dict[str, Any], factor_type: str = "standard") -> Dict[str, Any]:
    return {
        "risk_class": risk_class,
        "bucket": str(bucket),
        "risk_factor_id": factor_id,
        "market_group": group,
        "market_key": key,
        "tenor": tenor,
        "relative": relative,
        "factor_type": factor_type,
        "name": key if risk_class in {"GIRR", "FX"} else trade["underlying"],
        "curve": key,
        "location": "GLOBAL",
    }


def calculate_delta(trades: pd.DataFrame, market: Dict[str, Any]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for trade in trades.to_dict(orient="records"):
        base_value = price_trade_inr(trade, market)
        for factor in risk_factors_for_trade(trade):
            bump = 0.01 if factor["relative"] else 0.0001
            shocked = bumped_market(
                market, factor["market_group"], factor["market_key"], bump,
                factor["tenor"] if factor["market_group"] in {"rates", "credit_spreads"} else None,
                factor["relative"],
            )
            shocked_value = price_trade_inr(trade, shocked)
            rows.append({
                **_trade_labels(trade), **factor, "risk_measure": "DELTA",
                "base_value_inr": base_value, "shock_size": bump,
                "shocked_value_inr": shocked_value,
                "raw_sensitivity": (shocked_value - base_value) / bump,
            })
    return pd.DataFrame(rows)


def calculate_vega(trades: pd.DataFrame, market: Dict[str, Any]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for trade in trades.to_dict(orient="records"):
        if trade["instrument_type"] not in OPTIONAL_INSTRUMENTS:
            continue
        underlying = trade["underlying"]
        if underlying not in market["volatility"]:
            continue
        delta_factors = [factor for factor in risk_factors_for_trade(trade) if factor["risk_class"] != "FX" or trade["desk"] == "FX"]
        if not delta_factors:
            continue
        primary_class = ("GIRR" if trade["instrument_type"] == "SWAPTION" else
                         trade["csr_class"] if trade["csr_class"] != "NONE" else
                         "FX" if trade["desk"] == "FX" else
                         "COMMODITY" if trade["desk"] == "Commodity" else "EQUITY")
        primary = next(f for f in delta_factors if f["risk_class"] == primary_class)
        base_value = price_trade_inr(trade, market)
        shocked = bumped_market(market, "volatility", underlying, 0.01, relative=False)
        shocked_value = price_trade_inr(trade, shocked)
        sigma = float(market["volatility"][underlying])
        underlying_nodes = tenor_weights(float(trade["maturity_years"]), [0.5, 1, 3, 5, 10]) if primary_class == "GIRR" else [(None, 1.0)]
        for expiry, ew in tenor_weights(float(trade["option_expiry_years"]), [0.5, 1, 3, 5, 10]):
            for residual, uw in underlying_nodes:
                weight = ew * uw
                suffix = f"_UNDERLYING_{residual}Y" if residual is not None else ""
                rows.append({
                    **_trade_labels(trade), **primary, "risk_measure": "VEGA",
                    "risk_factor_id": f"{underlying}_VOL_{expiry}Y{suffix}",
                    "market_group": "volatility", "market_key": underlying, "relative": True,
                    "tenor": expiry, "underlying_tenor": residual,
                    "base_value_inr": base_value, "shock_size": 0.01,
                    "shocked_value_inr": base_value + (shocked_value - base_value) * weight,
                    "implied_volatility": sigma, "allocation_weight": weight,
                    "price_vega": (shocked_value - base_value) / 0.01 * weight,
                    "raw_sensitivity": (shocked_value - base_value) / 0.01 * sigma * weight,
                })
    return pd.DataFrame(rows)


def calculate_curvature(trades: pd.DataFrame, market: Dict[str, Any], delta: pd.DataFrame, risk_weight_function) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    options = trades[trades["instrument_type"].isin(OPTIONAL_INSTRUMENTS)]
    for trade in options.to_dict(orient="records"):
        trade_delta = delta[delta["trade_id"] == trade["trade_id"]]
        curve_groups = ["risk_class", "bucket", "market_group", "market_key"]
        for _, group in trade_delta.groupby(curve_groups, sort=False):
            delta_row = group.iloc[0].to_dict()
            factor = {key: delta_row[key] for key in [
                "risk_class", "bucket", "risk_factor_id", "market_group", "market_key",
                "tenor", "relative", "factor_type", "name", "curve", "location",
            ]}
            rw = risk_weight_function(factor, "DELTA")
            if factor["market_group"] == "rates":
                from frtb_engine.config import load_sbm_parameters
                rw = max(load_sbm_parameters()["delta_risk_weights"]["GIRR"]["tenors"].values())
            if factor["market_group"] in {"rates", "credit_spreads", "commodity_spot"}:
                factor["risk_factor_id"] = f"{factor['market_key']}_CURVE"
                factor["tenor"] = None
            if factor["market_group"] == "rates":
                up = bumped_market(market, "rates", factor["market_key"], rw, tenor=None, relative=False)
                down = bumped_market(market, "rates", factor["market_key"], -rw, tenor=None, relative=False)
            else:
                up = bumped_market(market, factor["market_group"], factor["market_key"], rw, relative=factor["relative"])
                down = bumped_market(market, factor["market_group"], factor["market_key"], -rw, relative=factor["relative"])
            base = price_trade_inr(trade, market)
            up_value = price_trade_inr(trade, up)
            down_value = price_trade_inr(trade, down)
            delta_effect = rw * float(group["raw_sensitivity"].sum())
            cvr_up = -(up_value - base - delta_effect)
            cvr_down = -(down_value - base + delta_effect)
            rows.append({
                **_trade_labels(trade), **factor, "risk_measure": "CURVATURE",
                "base_value_inr": base, "shock_size": rw,
                "shocked_value_inr": up_value, "down_value_inr": down_value,
                "curvature_up": cvr_up, "curvature_down": cvr_down,
                "raw_sensitivity": max(cvr_up, cvr_down, 0.0),
            })
    return pd.DataFrame(rows)


def _trade_labels(trade: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "trade_id": trade["trade_id"], "desk": trade["desk"],
        "sub_portfolio": trade["sub_portfolio"], "instrument_type": trade["instrument_type"],
        "product_form": trade["product_form"], "currency": trade["currency"],
    }
