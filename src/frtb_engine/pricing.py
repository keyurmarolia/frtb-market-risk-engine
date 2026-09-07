"""Readable educational pricing models used to generate FRTB sensitivities."""

from __future__ import annotations

import math
import numpy as np
from copy import deepcopy
from functools import lru_cache
from typing import Any, Dict

from scipy.stats import norm


def position_sign(trade: Dict[str, Any]) -> float:
    return 1.0 if str(trade["long_short"]).lower() == "long" else -1.0


def interpolate_curve(curve: Dict[Any, float], maturity: float) -> float:
    points = sorted((float(tenor), rate) for tenor, rate in curve.items())
    if maturity <= points[0][0]:
        return points[0][1]
    if maturity >= points[-1][0]:
        return points[-1][1]
    for (left_t, left_r), (right_t, right_r) in zip(points, points[1:]):
        if left_t <= maturity <= right_t:
            weight = (maturity - left_t) / (right_t - left_t)
            return left_r + weight * (right_r - left_r)
    raise ValueError(f"Curve interpolation failed for maturity {maturity}")


def black_scholes(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    option_type: str,
    carry: float = 0.0,
) -> float:
    if strike <= 0:
        raise ValueError("Option strike must be positive")
    if np.any(np.asarray(spot) <= 0):
        raise ValueError("Option spot must be positive")
    if maturity <= 0:
        intrinsic = np.maximum(spot - strike, 0.0) if option_type == "CALL" else np.maximum(strike - spot, 0.0)
        return intrinsic
    volatility = np.maximum(volatility, 1e-10)
    root_t = np.sqrt(maturity)
    d1 = (np.log(spot / strike) + (rate - carry + 0.5 * volatility**2) * maturity) / (volatility * root_t)
    d2 = d1 - volatility * root_t
    if option_type == "CALL":
        return spot * np.exp(-carry * maturity) * norm.cdf(d1) - strike * np.exp(-rate * maturity) * norm.cdf(d2)
    return strike * np.exp(-rate * maturity) * norm.cdf(-d2) - spot * np.exp(-carry * maturity) * norm.cdf(-d1)


def black76(forward: float, strike: float, maturity: float, rate: float, volatility: float, option_type: str) -> float:
    if strike <= 0:
        raise ValueError("Option strike must be positive")
    if np.any(np.asarray(forward) <= 0):
        raise ValueError("Option forward must be positive")
    if maturity <= 0:
        intrinsic = np.maximum(forward - strike, 0.0) if option_type == "CALL" else np.maximum(strike - forward, 0.0)
        return np.exp(-rate * maturity) * intrinsic
    volatility = np.maximum(volatility, 1e-10)
    root_t = np.sqrt(maturity)
    d1 = (np.log(np.maximum(forward, 1e-12) / strike) + 0.5 * volatility**2 * maturity) / (volatility * root_t)
    d2 = d1 - volatility * root_t
    call = np.exp(-rate * maturity) * (forward * norm.cdf(d1) - strike * norm.cdf(d2))
    if option_type == "CALL":
        return call
    return call - np.exp(-rate * maturity) * (forward - strike)


def fixed_rate_bond(notional: float, coupon: float, maturity: float, yield_rate: float) -> float:
    years = max(int(math.ceil(maturity)), 1)
    cashflows = 0.0
    for year in range(1, years + 1):
        time = min(float(year), maturity)
        coupon_cf = notional * coupon * (maturity - years + 1 if year == years and maturity < years else 1.0)
        cashflows += coupon_cf * np.exp(-yield_rate * time)
    return cashflows + notional * np.exp(-yield_rate * maturity)


def price_trade_local(trade: Dict[str, Any], market: Dict[str, Any]) -> float:
    kind = trade["instrument_type"]
    currency = trade["currency"]
    maturity = float(trade["maturity_years"])
    expiry = float(trade["option_expiry_years"])
    notional = float(trade["notional"])
    quantity = float(trade["quantity"])
    sign = position_sign(trade)
    underlying = trade["underlying"]
    strike = float(trade["strike"])
    option_type = trade["option_type"]
    rate = interpolate_curve(market["rates"].get(currency, market["rates"]["INR"]), max(maturity, expiry, 0.25))

    if kind == "BOND":
        return sign * fixed_rate_bond(notional, float(trade["coupon"]), maturity, rate)
    if kind == "CORPORATE_BOND":
        spread = curve_value(market["credit_spreads"][underlying], maturity)
        return sign * fixed_rate_bond(notional, float(trade["coupon"]), maturity, rate + spread)
    if kind == "INFLATION_BOND":
        inflation = (market["inflation"][currency])
        inflation_adjusted_notional = notional * np.exp(inflation * maturity)
        return sign * fixed_rate_bond(inflation_adjusted_notional, float(trade["coupon"]), maturity, rate)
    if kind == "IRS":
        market_rate = interpolate_curve(market["rates"][currency], maturity)
        return sign * notional * (market_rate - float(trade["fixed_rate"])) * maturity * np.exp(-rate * maturity)
    if kind == "FRA":
        market_rate = interpolate_curve(market["rates"][currency], maturity)
        return sign * notional * (market_rate - float(trade["fixed_rate"])) * maturity / (1.0 + market_rate * maturity)
    if kind == "SWAPTION":
        forward = interpolate_curve(market["rates"][currency], maturity)
        vol = (market["volatility"][underlying])
        annuity = sum(np.exp(-rate * year) for year in payment_times(maturity))
        return sign * notional * annuity * black76(forward, strike, expiry, 0.0, vol, option_type)
    if kind == "XCCY_BASIS_SWAP":
        basis = (market["cross_currency_basis"][underlying])
        pair = underlying.replace("_BASIS", "")
        first_currency, second_currency = pair[:3], pair[3:6]
        first_rate = interpolate_curve(market["rates"][first_currency], maturity)
        second_rate = interpolate_curve(market["rates"][second_currency], maturity)
        average_discount = 0.5 * (
            np.exp(-first_rate * maturity) + np.exp(-second_rate * maturity)
        )
        return sign * notional * (basis - float(trade["fixed_rate"])) * maturity * average_discount
    if kind == "CDS":
        spread = curve_value(market["credit_spreads"][underlying], maturity)
        return sign * notional * (float(trade["fixed_rate"]) - spread) * maturity * np.exp(-(rate + spread) * maturity)
    if kind == "CREDIT_OPTION":
        spread = curve_value(market["credit_spreads"][underlying], maturity)
        vol = (market["volatility"][underlying])
        # A fixed displacement keeps the transparent Black proxy defined when
        # the prescribed curvature shock takes a synthetic spread below zero.
        displacement = 0.05
        return sign * notional * black76(
            spread + displacement, strike + displacement, expiry, rate, vol, option_type
        )
    if kind == "CALLABLE_BOND":
        spread = curve_value(market["credit_spreads"][underlying], maturity)
        straight = fixed_rate_bond(notional, float(trade["coupon"]), maturity, rate + spread)
        vol = (market["volatility"][underlying])
        call_value = black_scholes(straight, notional * strike, expiry, rate, vol, "CALL")
        return sign * (straight - call_value)
    if kind in {"SECURITISATION_TRANCHE", "CTP_TRANCHE", "CTP_INDEX_HEDGE"}:
        spread = curve_value(market["credit_spreads"][underlying], maturity)
        base_price = (market["securitisation_price"][underlying])
        return sign * notional * np.maximum(base_price - spread * maturity * 0.5, 0.01)
    if kind == "EQUITY_CASH":
        return sign * quantity * (market["equity_spot"][underlying])
    if kind == "EQUITY_FUTURE":
        spot = market["equity_spot"][underlying]
        delivery = contract_terms(trade)["delivery_price"]
        return sign * quantity * (spot - delivery * np.exp(-rate * maturity))
    if kind in {"EQUITY_OPTION", "BARRIER_OPTION"}:
        spot = (market["equity_spot"][underlying])
        vol = (market["volatility"][underlying])
        value = quantity * black_scholes(spot, strike, expiry, rate, vol, option_type)
        if kind == "BARRIER_OPTION":
            barrier = contract_terms(trade)["barrier"]
            value = quantity * up_and_out_call(spot, strike, barrier, expiry, rate, vol)
        return sign * value
    if kind == "FX_FORWARD":
        spot = (market["fx"][underlying])
        foreign_rate = interpolate_curve(market["rates"][underlying[:3]], maturity)
        return sign * notional * (spot * np.exp(-foreign_rate * maturity) - strike * np.exp(-rate * maturity))
    if kind == "FX_OPTION":
        spot = (market["fx"][underlying])
        vol = (market["volatility"][underlying])
        foreign = underlying[:3]
        foreign_rate = interpolate_curve(market["rates"][foreign], expiry)
        return sign * notional * black_scholes(spot, strike, expiry, rate, vol, option_type, foreign_rate)
    if kind == "DIGITAL_OPTION":
        spot = (market["fx"][underlying])
        vol = (market["volatility"][underlying])
        root_t = np.sqrt(expiry)
        foreign_rate = interpolate_curve(market["rates"][underlying[:3]], expiry)
        d2 = (np.log(spot / strike) + (rate - foreign_rate - 0.5 * vol**2) * expiry) / (vol * root_t)
        probability = norm.cdf(d2) if option_type == "CALL" else norm.cdf(-d2)
        return sign * notional * np.exp(-rate * expiry) * probability
    if kind == "COMMODITY_FUTURE":
        return sign * quantity * (market["commodity_spot"][underlying] - contract_terms(trade)["delivery_price"])
    if kind == "COMMODITY_OPTION":
        spot = (market["commodity_spot"][underlying])
        vol = (market["volatility"][underlying])
        return sign * quantity * black_scholes(spot, strike, expiry, rate, vol, option_type)
    if kind == "WEATHER_DERIVATIVE":
        index_value = (market["weather_index_value"][underlying])
        return sign * notional * (index_value - 0.50)
    if kind == "REALIZED_VOL_SWAP":
        realised = (market["realized_volatility"][underlying])
        return sign * notional * (realised - strike)
    raise ValueError(f"Unsupported instrument type: {kind}")


def price_trade_inr(trade: Dict[str, Any], market: Dict[str, Any]) -> float:
    local_value = price_trade_local(trade, market)
    currency = trade["currency"]
    if currency == "INR":
        return local_value
    pair = f"{currency}INR"
    return local_value * (market["fx"][pair])


def bumped_market(market: Dict[str, Any], group: str, key: str, bump: float, tenor: float | None = None, relative: bool = False) -> Dict[str, Any]:
    shocked = deepcopy(market)
    if group in {"rates", "credit_spreads"}:
        curve = shocked[group][key]
        if not isinstance(curve, dict):
            curve = {t: curve for t in [0.5, 1.0, 3.0, 5.0, 10.0]}
            shocked[group][key] = curve
        if tenor is None:
            for curve_tenor in curve:
                curve[curve_tenor] = float(curve[curve_tenor]) + bump
        else:
            matching_key = min(curve, key=lambda value: abs(float(value) - float(tenor)))
            curve[matching_key] = float(curve[matching_key]) + bump
        return shocked
    old = float(shocked[group][key])
    shocked[group][key] = old * (1.0 + bump) if relative else old + bump
    return shocked


def curve_value(value, maturity):
    return interpolate_curve(value, maturity) if isinstance(value, dict) else value


def payment_times(maturity):
    return [min(float(i), maturity) for i in range(1, max(math.ceil(maturity), 1) + 1)]


def contract_terms(trade):
    return _contract_terms_by_trade().get(trade["trade_id"], {})


@lru_cache(maxsize=1)
def _contract_terms_by_trade():
    from frtb_engine.config import load_synthetic_assumptions
    return load_synthetic_assumptions()["contract_terms"]


def up_and_out_call(spot, strike, barrier, maturity, rate, volatility):
    """Continuously monitored, zero-rebate upper barrier; strike below barrier.

    Integrate the lognormal transition density killed at the upper barrier.
    Gauss-Legendre quadrature is deterministic and supports scenario arrays.
    """
    if maturity <= 0:
        intrinsic = np.maximum(np.asarray(spot) - strike, 0.0)
        result = np.where(np.asarray(spot) >= barrier, 0.0, intrinsic)
        return float(result) if np.ndim(spot) == 0 else result
    if not 0 < strike < barrier:
        raise ValueError("Upper-barrier call requires 0 < strike < barrier")
    nodes, weights = np.polynomial.legendre.leggauss(32)
    x = np.log(np.maximum(np.asarray(spot), 1e-12) / barrier)
    vol = np.maximum(np.asarray(volatility), 1e-8)
    drift = rate - 0.5 * vol**2
    low = np.log(strike / barrier)
    y = low * (1 - nodes) / 2
    sd = vol * np.sqrt(maturity)
    a = (y[:, None] - np.atleast_1d(x + drift * maturity)) / np.atleast_1d(sd)
    b = (y[:, None] - np.atleast_1d(-x + drift * maturity)) / np.atleast_1d(sd)
    reflected = np.exp(np.clip(-2 * drift * x / vol**2, -700, 700))
    density = (norm.pdf(a) - np.atleast_1d(reflected) * norm.pdf(b)) / np.atleast_1d(sd)
    payoff = barrier * np.exp(y) - strike
    result = np.exp(-rate * maturity) * (-low / 2) * np.sum(weights[:, None] * payoff[:, None] * density, axis=0)
    result = np.where(np.asarray(spot) >= barrier, 0.0, np.maximum(result, 0.0))
    return float(result[0]) if np.ndim(spot) == 0 and np.ndim(rate) == 0 and np.ndim(volatility) == 0 else result
