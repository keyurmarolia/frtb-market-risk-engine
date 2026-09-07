"""Default risk charge calculations kept separate for the three Basel classes."""

from __future__ import annotations

from typing import Dict, List
import math

import pandas as pd

from frtb_engine.config import load_drc_parameters, load_market_data, load_synthetic_assumptions


def calculate_drc(trades: pd.DataFrame, valuations: pd.DataFrame, market=None) -> Dict[str, pd.DataFrame | float]:
    market = load_market_data() if market is None else market
    merged = trades.merge(valuations[["trade_id", "market_value_inr"]], on="trade_id", how="left")
    ordinary = merged[(merged["drc_class"] == "NON_SECURITISATION") | merged["instrument_type"].isin(["BOND", "INFLATION_BOND", "EQUITY_OPTION", "BARRIER_OPTION", "EQUITY_FUTURE"])]
    nonsec = _non_securitisation(ordinary, market)
    nonctp = _securitisation_non_ctp(merged[merged["drc_class"] == "SECURITISATION_NON_CTP"])
    ctp = _securitisation_ctp(merged[merged["drc_class"] == "SECURITISATION_CTP"])
    total = float(nonsec["capital"] + nonctp["capital"] + ctp["capital"])
    summary = pd.DataFrame([
        {"drc_class": "NON_SECURITISATION", "capital": nonsec["capital"]},
        {"drc_class": "SECURITISATION_NON_CTP", "capital": nonctp["capital"]},
        {"drc_class": "SECURITISATION_CTP", "capital": ctp["capital"]},
        {"drc_class": "TOTAL_DRC", "capital": total},
    ])
    return {
        "gross_jtd": pd.concat([nonsec["gross"], nonctp["gross"], ctp["gross"]], ignore_index=True),
        "net_jtd": pd.concat([nonsec["net"], nonctp["net"], ctp["net"]], ignore_index=True),
        "bucket_results": pd.concat([nonsec["buckets"], nonctp["buckets"], ctp["buckets"]], ignore_index=True),
        "summary": summary,
        "drc_capital": total,
    }


def _non_securitisation(frame: pd.DataFrame, market=None) -> Dict:
    params = load_drc_parameters()["non_securitisation"]
    market = load_market_data() if market is None else market
    rows: List[Dict] = []
    for trade in frame.to_dict(orient="records"):
        seniority = trade["seniority"]
        if seniority == "EQUITY" or seniority == "SUBORDINATED":
            lgd = float(params["lgd"]["equity_and_non_senior_debt"])
        elif seniority == "COVERED_BOND":
            lgd = float(params["lgd"]["covered_bond"])
        else:
            lgd = float(params["lgd"]["senior_debt"])
        scale = 1.0 if trade["instrument_type"] == "EQUITY_CASH" else min(max(float(trade["maturity_years"]), float(trade["option_expiry_years"]), 0.25), 1.0)
        jtd = default_loss(trade, market, lgd) * scale
        rating = str(trade["rating"]).upper().replace("-", "").replace("+", "")
        if rating not in params["risk_weights"]:
            rating = "UNRATED"
        rows.append({
            "trade_id": trade["trade_id"], "drc_class": "NON_SECURITISATION",
            "bucket": "SOVEREIGN" if trade["sector"] == "SOVEREIGN" else "CORPORATE", "obligor": trade["issuer"],
            "rating": rating, "seniority": seniority, "maturity_scale": scale,
            "lgd": lgd, "gross_jtd": jtd,
            "risk_weight": float(params["risk_weights"][rating]),
        })
    gross = pd.DataFrame(rows)
    if gross.empty:
        return _empty_result(gross)
    net = seniority_netting(gross)
    buckets = _hbr_buckets(net, floor_at_zero=True)
    return {"gross": gross, "net": net, "buckets": buckets, "capital": float(buckets["capital"].sum())}


def _securitisation_non_ctp(frame: pd.DataFrame) -> Dict:
    rows = []
    for trade in frame.to_dict(orient="records"):
        sign = 1.0 if trade["long_short"] == "long" else -1.0
        scale = min(max(float(trade["maturity_years"]), 0.25), 1.0)
        rows.append({
            "trade_id": trade["trade_id"], "drc_class": "SECURITISATION_NON_CTP",
            "bucket": trade["drc_bucket"], "obligor": trade["underlying"],
            "rating": trade["rating"], "seniority": trade["seniority"], "maturity_scale": scale,
            "attachment": trade["attachment"], "detachment": trade["detachment"],
            "lgd": 0.0, "gross_jtd": sign * abs(float(trade["market_value_inr"])) * scale,
            "risk_weight": securitisation_weight(trade),
        })
    gross = pd.DataFrame(rows)
    if gross.empty:
        return _empty_result(gross)
    net = gross.groupby(["drc_class", "bucket", "obligor", "rating", "attachment", "detachment", "seniority"], as_index=False).agg(
        net_jtd=("gross_jtd", "sum"), risk_weight=("risk_weight", "max")
    )
    buckets = _hbr_buckets(net, floor_at_zero=True)
    return {"gross": gross, "net": net, "buckets": buckets, "capital": float(buckets["capital"].sum())}


def _securitisation_ctp(frame: pd.DataFrame) -> Dict:
    params = load_drc_parameters()["securitisation_ctp"]
    rows = []
    for trade in frame.to_dict(orient="records"):
        sign = 1.0 if trade["long_short"] == "long" else -1.0
        weight = securitisation_weight(trade) if trade["instrument_type"] != "CTP_INDEX_HEDGE" else 0.0
        if trade["instrument_type"] == "CTP_INDEX_HEDGE":
            weight = load_drc_parameters()["non_securitisation"]["risk_weights"].get(trade["rating"], 0.15)
        rows.append({
            "trade_id": trade["trade_id"], "drc_class": "SECURITISATION_CTP",
            "bucket": trade["drc_bucket"], "obligor": trade["underlying"],
            "rating": trade["rating"], "seniority": trade["seniority"], "maturity_scale": 1.0,
            "attachment": trade["attachment"], "detachment": trade["detachment"],
            "lgd": 0.0, "gross_jtd": sign * abs(float(trade["market_value_inr"])),
            "risk_weight": float(weight),
        })
    gross = pd.DataFrame(rows)
    if gross.empty:
        return _empty_result(gross)
    net = gross.groupby(["drc_class", "bucket", "obligor", "rating", "attachment", "detachment"], as_index=False).agg(
        net_jtd=("gross_jtd", "sum"), risk_weight=("risk_weight", "max")
    )
    total_long = float(net.loc[net["net_jtd"] > 0, "net_jtd"].sum())
    total_short = abs(float(net.loc[net["net_jtd"] < 0, "net_jtd"].sum()))
    hbr = total_long / (total_long + total_short) if total_long + total_short else 0.0
    bucket_rows = []
    for bucket, data in net.groupby("bucket"):
        weighted_long = float((data.loc[data["net_jtd"] > 0, "net_jtd"] * data.loc[data["net_jtd"] > 0, "risk_weight"]).sum())
        weighted_short = abs(float((data.loc[data["net_jtd"] < 0, "net_jtd"] * data.loc[data["net_jtd"] < 0, "risk_weight"]).sum()))
        bucket_rows.append({
            "drc_class": "SECURITISATION_CTP", "bucket": bucket,
            "net_long_jtd": total_long, "net_short_jtd": -total_short, "hbr": hbr,
            "weighted_long": weighted_long, "weighted_short": weighted_short,
            "capital": weighted_long - hbr * weighted_short,
        })
    buckets = pd.DataFrame(bucket_rows)
    positive = float(buckets.loc[buckets["capital"] >= 0, "capital"].sum())
    negative = float(buckets.loc[buckets["capital"] < 0, "capital"].sum())
    capital = max(positive + float(params["cross_index_hedge_discount"]) * negative, 0.0)
    return {"gross": gross, "net": net, "buckets": buckets, "capital": capital}


def _hbr_buckets(net: pd.DataFrame, floor_at_zero: bool) -> pd.DataFrame:
    rows = []
    for bucket, data in net.groupby("bucket"):
        longs = data[data["net_jtd"] > 0]
        shorts = data[data["net_jtd"] < 0]
        net_long = float(longs["net_jtd"].sum())
        net_short = float(shorts["net_jtd"].sum())
        hbr = net_long / (net_long + abs(net_short)) if net_long + abs(net_short) else 0.0
        weighted_long = float((longs["net_jtd"] * longs["risk_weight"]).sum())
        weighted_short = abs(float((shorts["net_jtd"] * shorts["risk_weight"]).sum()))
        capital = weighted_long - hbr * weighted_short
        if floor_at_zero:
            capital = max(capital, 0.0)
        rows.append({
            "drc_class": data["drc_class"].iloc[0], "bucket": bucket,
            "net_long_jtd": net_long, "net_short_jtd": net_short, "hbr": hbr,
            "weighted_long": weighted_long, "weighted_short": weighted_short,
            "capital": capital,
        })
    return pd.DataFrame(rows)


def _empty_result(gross: pd.DataFrame) -> Dict:
    return {"gross": gross, "net": pd.DataFrame(), "buckets": pd.DataFrame(), "capital": 0.0}


def default_loss(trade, market, lgd=0.75):
    """Signed current value minus contractual value immediately after default."""
    from frtb_engine.pricing import price_trade_inr
    sign = 1.0 if trade["long_short"] == "long" else -1.0
    fx = 1.0 if trade["currency"] == "INR" else float(market["fx"][f"{trade['currency']}INR"])
    value = price_trade_inr(trade, market)
    kind = trade["instrument_type"]
    if kind == "EQUITY_FUTURE":
        return sign * float(trade["quantity"]) * float(market["equity_spot"][trade["underlying"]]) * fx
    if kind in {"EQUITY_CASH", "EQUITY_OPTION", "BARRIER_OPTION"}:
        settlement = float(trade["quantity"]) * float(trade["strike"]) if trade["option_type"] == "PUT" else 0.0
        return value - sign * settlement * fx
    if kind == "CDS":
        return value + sign * float(trade["notional"]) * fx * lgd
    if kind == "CREDIT_OPTION":
        settlement = float(trade["notional"]) * lgd if trade["option_type"] == "CALL" else 0.0
        return value - sign * settlement * fx
    return value - sign * float(trade["notional"]) * fx * (1 - lgd)


def seniority_netting(gross):
    """A short offsets a long only at equal or lower credit seniority (MAR22.19)."""
    rank = {"COVERED_BOND": 0, "SENIOR": 1, "SUBORDINATED": 2, "EQUITY": 3}
    result = []
    keys = ["drc_class", "bucket", "obligor", "rating"]
    for _, group in gross.groupby(keys, sort=False):
        rows = group.groupby("seniority", as_index=False).agg(net_jtd=("gross_jtd", "sum"), risk_weight=("risk_weight", "max")).to_dict("records")
        for short in sorted(rows, key=lambda r: rank[r["seniority"]]):
            if short["net_jtd"] >= 0:
                continue
            for long in sorted(rows, key=lambda r: rank[r["seniority"]], reverse=True):
                if long["net_jtd"] <= 0 or rank[short["seniority"]] < rank[long["seniority"]]:
                    continue
                offset = min(long["net_jtd"], -short["net_jtd"])
                long["net_jtd"] -= offset
                short["net_jtd"] += offset
        result.extend({**{k: group.iloc[0][k] for k in keys}, **r} for r in rows)
    return pd.DataFrame(result)


def securitisation_weight(trade):
    """SEC-SA capital ratio from synthetic pool inputs; RWA weight divided by 12.5."""
    pool = load_synthetic_assumptions()["securitisation_pools"][trade["issuer"]]
    a, d = float(trade["attachment"]), float(trade["detachment"])
    if not 0 <= a < d <= 1:
        raise ValueError("Tranche attachment/detachment must satisfy 0 <= A < D <= 1")
    rules = load_drc_parameters()["securitisation_non_ctp"]
    p = float(rules["sec_sa_supervisory_parameter_p"])
    ka = (1 - pool["delinquent_share"]) * pool["pool_capital_ratio"] + pool["delinquent_share"] * 0.5
    if d <= ka:
        capital = float(rules["below_ka_capital_weight"])
    else:
        exponent = -1 / (p * ka)
        u, lower = d - ka, max(a - ka, 0.0)
        kssfa = (math.exp(exponent * u) - math.exp(exponent * lower)) / (exponent * (u - lower))
        capital = kssfa if a >= ka else (ka - a + (d - ka) * kssfa) / (d - a)
    return min(max(capital, float(rules["sec_sa_rwa_floor"]) / 12.5), 1.0)
