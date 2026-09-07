"""Transparent FRTB Internal Models Approach calculations.

The functions keep factor, desk, date and trade labels visible.  Synthetic
history is generated from correlated economic factors and explicit market
regimes; it is deterministic and is never presented as observed market data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, norm, spearmanr, t

from frtb_engine.config import load_ima_parameters, load_synthetic_assumptions, load_market_data
from frtb_engine.drc import calculate_drc
from frtb_engine.pipeline import _price_book
from frtb_engine.sensitivities import calculate_delta, calculate_vega


RISK_CLASS_MAP = {
    "GIRR": "INTEREST_RATE",
    "CSR_NON_SECURITISATION": "CREDIT_SPREAD",
    "CSR_SECURITISATION_NON_CTP": "CREDIT_SPREAD",
    "CSR_SECURITISATION_CTP": "CREDIT_SPREAD",
    "EQUITY": "EQUITY", "FX": "FX", "COMMODITY": "COMMODITY",
}
REGIME_WINDOWS = (
    ("2018-09-01", "2018-12-31", 1.55, "global_risk_repricing"),
    ("2020-02-20", "2020-06-30", 3.10, "pandemic_stress"),
    ("2022-02-01", "2022-10-31", 1.85, "inflation_and_rate_stress"),
    ("2024-07-01", "2024-10-31", 1.35, "commodity_fx_volatility"),
)


@dataclass(frozen=True)
class ESResult:
    es_10_day: float
    liquidity_horizon_adjusted_es: float
    components: list[dict[str, float]]


def build_factor_inventory(
    trades: pd.DataFrame,
    market: Dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build one common inventory and desk-factor exposure table from SA mappings."""
    delta = calculate_delta(trades, market)
    vega = calculate_vega(trades, market)
    exposures = pd.concat([
        delta.assign(ima_risk_measure="DELTA"),
        vega.assign(ima_risk_measure="VEGA"),
    ], ignore_index=True, sort=False)
    exposures["broad_risk_class"] = exposures["risk_class"].map(RISK_CLASS_MAP)
    exposures["source_risk_class"] = exposures["risk_class"]
    trade_labels = trades[[
        "trade_id", "rating", "sector", "economy", "market_cap", "underlying",
    ]]
    exposures = exposures.merge(trade_labels, on="trade_id", how="left")
    exposures["exposure_key"] = exposures["desk"] + "|" + exposures["risk_factor_id"]

    rows: list[dict[str, Any]] = []
    for factor_id, group in exposures.groupby("risk_factor_id", sort=True):
        first = group.iloc[0]
        category, horizon = _liquidity_category(first)
        profile = _observation_profile(first)
        rows.append({
            "risk_factor_id": factor_id,
            "broad_risk_class": first["broad_risk_class"],
            "source_risk_class": first["risk_class"],
            "market_group": first["market_group"],
            "market_key": first["market_key"],
            "tenor_years": first.get("tenor", np.nan),
            "factor_type": first.get("factor_type", "standard"),
            "desks": ", ".join(sorted(group["desk"].unique())),
            "trade_count": int(group["trade_id"].nunique()),
            "signed_sensitivity_inr": float(group["raw_sensitivity"].sum()),
            "absolute_sensitivity_inr": float(group["raw_sensitivity"].abs().sum()),
            "liquidity_category": category,
            "liquidity_horizon_days": horizon,
            "rfet_observation_profile": profile,
            "valuation_anchor_value": _market_anchor(market, first),
            "input_data_status": "SYNTHETIC_MARKET_HISTORY",
            "input_explanation": "Correlated, regime-aware history anchored to the shared valuation snapshot",
        })
    inventory = pd.DataFrame(rows)
    keep = [
        "trade_id", "desk", "sub_portfolio", "instrument_type", "risk_factor_id",
        "broad_risk_class", "source_risk_class", "ima_risk_measure", "market_group",
        "market_key", "tenor", "rating", "sector", "economy", "market_cap",
        "raw_sensitivity", "base_value_inr", "price_vega", "allocation_weight",
    ]
    return inventory, exposures[keep].copy()


def _market_anchor(market: Dict[str, Any], row: pd.Series) -> float:
    group = str(row["market_group"])
    key = str(row["market_key"])
    if group in {"rates", "credit_spreads"} and isinstance(market[group][key], dict):
        curve = market[group][key]
        tenor = float(row["tenor"])
        return float(curve.get(tenor, curve.get(str(tenor), min(curve.values()))))
    if group in market and key in market[group]:
        return float(market[group][key])
    return 1.0


def _liquidity_category(row: pd.Series) -> tuple[str, int]:
    risk_class = row["broad_risk_class"]
    measure = row.get("ima_risk_measure", "DELTA")
    key = str(row.get("market_key", ""))
    rating = str(row.get("rating", "UNRATED"))
    market_cap = str(row.get("market_cap", "LARGE"))
    mapping = load_ima_parameters()["liquidity_horizon_mapping"]
    def category(name):
        return name, int(mapping[name])
    if risk_class == "INTEREST_RATE":
        specified = {"INR", "USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF"}
        return category("INTEREST_RATE_VOLATILITY" if measure == "VEGA" else "INTEREST_RATE_SPECIFIED_CURRENCY" if str(row.get("bucket", key)) in specified else "INTEREST_RATE_OTHER")
    if risk_class == "CREDIT_SPREAD":
        if measure == "VEGA":
            return category("CREDIT_SPREAD_VOLATILITY")
        if row.get("risk_class") != "CSR_NON_SECURITISATION":
            return category("CREDIT_SPREAD_OTHER")
        if row.get("sector") == "SOVEREIGN":
            return category("CREDIT_SPREAD_SOVEREIGN_IG" if rating in {"AAA", "AA", "A", "BBB"} else "CREDIT_SPREAD_SOVEREIGN_HY")
        if rating in {"AAA", "AA", "A", "BBB"}:
            return "CREDIT_SPREAD_CORPORATE_IG", 40
        if rating in {"BB", "B", "CCC"}:
            return "CREDIT_SPREAD_CORPORATE_HY", 60
        return "CREDIT_SPREAD_OTHER", 120
    if risk_class == "EQUITY":
        if measure == "VEGA":
            return ("EQUITY_SMALL_CAP_VOLATILITY", 60) if market_cap == "SMALL" else ("EQUITY_LARGE_CAP_VOLATILITY", 20)
        return ("EQUITY_SMALL_CAP_PRICE", 20) if market_cap == "SMALL" else ("EQUITY_LARGE_CAP_PRICE", 10)
    if risk_class == "FX":
        specified_currencies = {"USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF", "MXN", "CNY", "NZD", "RUB", "HKD", "SGD", "TRY", "KRW", "SEK", "ZAR", "INR", "NOK", "BRL"}
        pair = "FX_SPECIFIED_PAIR" if key[:3] in specified_currencies and key[3:] in specified_currencies else "FX_OTHER_PAIR"
        return category("FX_VOLATILITY" if measure == "VEGA" else pair)
    if risk_class == "COMMODITY":
        is_energy = key in {"BRENT", "WTI"}
        if measure == "VEGA":
            return ("COMMODITY_ENERGY_VOLATILITY", 60) if is_energy else ("COMMODITY_METAL_VOLATILITY", 60)
        return ("COMMODITY_ENERGY_PRICE", 20) if is_energy else ("COMMODITY_METAL_PRICE", 20)
    return "COMMODITY_OTHER", 120


def _observation_profile(row: pd.Series) -> str:
    factor = str(row["risk_factor_id"])
    source_class = str(row["risk_class"])
    illiquid_tokens = ("INDIA_SMALLCAP", "INDIA_METALS", "RMBS", "3_7", "EU_UTILITY_VOL")
    if any(token in factor for token in illiquid_tokens):
        return "SPARSE_FAIL"
    if source_class.startswith("CSR") or row.get("ima_risk_measure") == "VEGA":
        return "REGULAR_24_ROUTE"
    return "FREQUENT_100_ROUTE"


def generate_realistic_history(
    inventory: pd.DataFrame,
    start: str = "2016-07-01",
    end: str = "2026-06-30",
    seed: int = 20260825,
) -> pd.DataFrame:
    """Generate correlated factor history with volatility clustering and named regimes."""
    dates = pd.bdate_range(start, end)
    n_dates, n_factors = len(dates), len(inventory)
    rng = np.random.default_rng(seed)
    classes = ["INTEREST_RATE", "CREDIT_SPREAD", "EQUITY", "FX", "COMMODITY"]
    correlation = np.array([
        [1.00, 0.25, -0.18, 0.08, 0.12],
        [0.25, 1.00, -0.42, 0.18, 0.20],
        [-0.18, -0.42, 1.00, -0.12, 0.22],
        [0.08, 0.18, -0.12, 1.00, 0.18],
        [0.12, 0.20, 0.22, 0.18, 1.00],
    ])
    chol = np.linalg.cholesky(correlation)
    common = rng.standard_t(df=6, size=(n_dates, len(classes))) / np.sqrt(6 / 4)
    common = common @ chol.T
    regime_scale = np.ones(n_dates)
    regime_name = np.full(n_dates, "ordinary_market", dtype=object)
    for start_date, end_date, scale, name in REGIME_WINDOWS:
        mask = (dates >= start_date) & (dates <= end_date)
        regime_scale[mask] = scale
        regime_name[mask] = name
    persistence = np.ones(n_dates)
    for index in range(1, n_dates):
        shock = float(np.mean(np.abs(common[index - 1])))
        persistence[index] = 0.92 * persistence[index - 1] + 0.08 * max(0.75, shock)
    volatility_state = np.clip(regime_scale * persistence, 0.65, 4.5)

    records: list[pd.DataFrame] = []
    for position, factor in inventory.reset_index(drop=True).iterrows():
        class_index = classes.index(factor["broad_risk_class"])
        idiosyncratic = rng.standard_t(df=7, size=n_dates) / np.sqrt(7 / 5)
        innovation = (0.78 * common[:, class_index] + 0.22 * idiosyncratic) * volatility_state
        scale, change_type, anchor = _factor_dynamics(factor)
        changes = innovation * scale
        if change_type == "RELATIVE":
            changes = np.clip(changes, -0.20, 0.20)
            level = anchor * np.exp(np.cumsum(changes) - np.cumsum(changes)[-1])
            changes = np.r_[0.0, level[1:] / level[:-1] - 1.0]
        else:
            raw_level = anchor + np.cumsum(changes) - np.cumsum(changes)[-1]
            floor = 0.0001 if factor["market_group"] in {"rates", "credit_spreads", "volatility"} else -1.0
            level = np.maximum(raw_level, floor)
            changes = np.r_[0.0, np.diff(level)]
        records.append(pd.DataFrame({
            "date": dates,
            "risk_factor_id": factor["risk_factor_id"],
            "broad_risk_class": factor["broad_risk_class"],
            "daily_change": changes,
            "change_type": change_type,
            "level": level,
            "market_regime": regime_name,
            "volatility_state": volatility_state,
            "data_status": "SYNTHETIC_REGIME_AWARE",
        }))
    return pd.concat(records, ignore_index=True)


def _factor_dynamics(factor: pd.Series) -> tuple[float, str, float]:
    group = factor["market_group"]
    factor_id = str(factor["risk_factor_id"])
    anchor = float(factor.get("valuation_anchor_value", 1.0))
    if group == "rates":
        return 0.00028, "ABSOLUTE", anchor
    if group == "inflation":
        return 0.00022, "ABSOLUTE", anchor
    if group == "cross_currency_basis":
        return 0.00006, "ABSOLUTE", anchor
    if group == "credit_spreads":
        return 0.00065, "ABSOLUTE", anchor
    if group == "volatility":
        return 0.0045, "ABSOLUTE", anchor
    if group == "fx":
        return 0.0048, "RELATIVE", anchor
    if group == "equity_spot":
        return 0.0125, "RELATIVE", anchor
    if group == "commodity_spot":
        return 0.0140, "RELATIVE", anchor
    return 0.0080, "RELATIVE", anchor


def generate_rpo_observations(
    inventory: pd.DataFrame,
    start: str = "2025-07-01",
    end: str = "2026-06-30",
    seed: int = 20260826,
) -> pd.DataFrame:
    """Create explicitly synthetic transaction/committed-quote evidence for RFET teaching."""
    dates = pd.bdate_range(start, end)
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for _, factor in inventory.iterrows():
        profile = factor["rfet_observation_profile"]
        if profile == "FREQUENT_100_ROUTE":
            count = 118
            selected = np.linspace(0, len(dates) - 1, count, dtype=int)
            evidence = "SYNTHETIC_ARM_LENGTH_TRANSACTION"
        elif profile == "REGULAR_24_ROUTE":
            count = 32
            selected = np.linspace(0, len(dates) - 1, count, dtype=int)
            evidence = "SYNTHETIC_COMMITTED_QUOTE"
        else:
            count = 14
            selected = np.sort(rng.choice(np.arange(0, len(dates) // 2), count, replace=False))
            evidence = "SYNTHETIC_ARM_LENGTH_TRANSACTION"
        for sequence, date_index in enumerate(selected, start=1):
            rows.append({
                "risk_factor_id": factor["risk_factor_id"],
                "observation_date": dates[date_index],
                "evidence_type": evidence,
                "observation_reference": f"RPO-{factor['risk_factor_id']}-{sequence:03d}",
                "qualifying_real_price": True,
                "data_status": "SYNTHETIC_RFET_EVIDENCE",
                "data_explanation": "Synthetic transaction or committed-quote event; not an observed public closing price",
            })
    return pd.DataFrame(rows)


def evaluate_rfet(inventory: pd.DataFrame, observations: pd.DataFrame, as_of=None) -> pd.DataFrame:
    params = load_ima_parameters()["rfet"]
    window_end = pd.Timestamp(as_of or load_market_data()["valuation_date"])
    window_start = window_end - pd.DateOffset(years=1) + pd.Timedelta(1, unit="D")
    rows: list[dict[str, Any]] = []
    for _, factor in inventory.iterrows():
        factor_obs = observations[
            (observations["risk_factor_id"] == factor["risk_factor_id"])
            & observations["qualifying_real_price"]
        ].copy()
        factor_obs["observation_date"] = pd.to_datetime(factor_obs["observation_date"])
        factor_obs = factor_obs[(factor_obs["observation_date"] >= window_start) & (factor_obs["observation_date"] <= window_end)]
        unique_dates = pd.DatetimeIndex(sorted(factor_obs["observation_date"].dt.normalize().unique()))
        minimum_90 = _minimum_observations_in_rolling_days(unique_dates, window_start, window_end, 90)
        count = len(unique_dates)
        route_1 = count >= params["route_1_minimum_observations"] and minimum_90 >= params["route_1_minimum_observations_in_any_90_days"]
        route_2 = count >= params["route_2_minimum_observations"]
        passed = bool(route_1 or route_2)
        route = "100_OBSERVATION_ROUTE" if route_2 else ("24_PLUS_CONTINUITY_ROUTE" if route_1 else "NO_ROUTE_PASSED")
        if passed:
            reason = f"Passed {route.replace('_', ' ').lower()} with {count} qualifying dates"
        else:
            reason = f"Failed: {count} qualifying dates and minimum {minimum_90} observations in a 90-day window"
        rows.append({
            "risk_factor_id": factor["risk_factor_id"],
            "broad_risk_class": factor["broad_risk_class"],
            "qualifying_observation_count": count,
            "minimum_observations_in_any_90_days": minimum_90,
            "route_1_pass": route_1,
            "route_2_pass": route_2,
            "rfet_pass": passed,
            "rfet_route": route,
            "modellability_status": "MRF" if passed else "NMRF",
            "rfet_reason": reason,
            "evidence_data_status": "SYNTHETIC_RFET_EVIDENCE",
        })
    return pd.DataFrame(rows)


def _minimum_observations_in_rolling_days(
    dates: pd.DatetimeIndex,
    start: pd.Timestamp,
    end: pd.Timestamp,
    days: int,
) -> int:
    if len(dates) == 0:
        return 0
    window_span = pd.Timedelta(int(days), unit="D")
    anchors = pd.date_range(start, end - pd.Timedelta(int(days) - 1, unit="D"), freq="D")
    counts = [int(((dates >= anchor) & (dates < anchor + window_span)).sum()) for anchor in anchors]
    return min(counts) if counts else 0


def build_factor_pnl(
    history: pd.DataFrame,
    exposures: pd.DataFrame,
    inventory: pd.DataFrame,
) -> pd.DataFrame:
    from frtb_engine.scenarios import factor_revaluations
    from frtb_engine.sensitivities import load_trades
    return factor_revaluations(history, exposures, inventory, load_trades(), load_market_data())


def expected_shortfall(pnl: pd.Series | np.ndarray, confidence: float = 0.975) -> float:
    values = np.asarray(pnl, dtype=float)
    losses = -values[np.isfinite(values)]
    if losses.size == 0:
        return 0.0
    threshold = float(np.quantile(losses, confidence, method="linear"))
    tail = losses[losses >= threshold]
    return float(max(tail.mean() if tail.size else threshold, 0.0))


def liquidity_horizon_es(
    factor_pnl: pd.DataFrame,
    inventory: pd.DataFrame,
    factors: Iterable[str],
    confidence: float = 0.975,
) -> ESResult:
    selected = set(factors)
    frame = factor_pnl[factor_pnl["risk_factor_id"].isin(selected)].copy()
    if frame.empty:
        return ESResult(0.0, 0.0, [])
    daily_all = frame.groupby("date")["factor_pnl_inr"].sum().sort_index()
    base_pnl = daily_all.rolling(10).sum().dropna()
    base_es = expected_shortfall(base_pnl, confidence)
    components = [{"liquidity_horizon_days": 10, "subset_es_inr": base_es, "scaling_increment": 1.0, "squared_contribution": base_es ** 2}]
    squared = base_es ** 2
    previous = 10
    factor_lh = inventory.set_index("risk_factor_id")["liquidity_horizon_days"].to_dict()
    for horizon in (20, 40, 60, 120):
        subset = {factor for factor in selected if int(factor_lh.get(factor, 10)) >= horizon}
        if subset:
            daily = frame[frame["risk_factor_id"].isin(subset)].groupby("date")["factor_pnl_inr"].sum().sort_index()
            subset_es = expected_shortfall(daily.rolling(10).sum().dropna(), confidence)
        else:
            subset_es = 0.0
        increment = (horizon - previous) / 10.0
        contribution = subset_es ** 2 * increment
        squared += contribution
        components.append({"liquidity_horizon_days": horizon, "subset_es_inr": subset_es, "scaling_increment": increment, "squared_contribution": contribution})
        previous = horizon
    return ESResult(base_es, float(np.sqrt(squared)), components)


def select_reduced_factors(
    factor_pnl: pd.DataFrame,
    rfet: pd.DataFrame,
    target: float = 0.85,
) -> pd.DataFrame:
    mrf = set(rfet.loc[rfet["modellability_status"] == "MRF", "risk_factor_id"])
    materiality = factor_pnl[factor_pnl["risk_factor_id"].isin(mrf)].groupby([
        "broad_risk_class", "risk_factor_id"
    ])["factor_pnl_inr"].apply(lambda values: float(np.mean(np.abs(values)))).rename("mean_absolute_daily_pnl_inr").reset_index()
    rows = []
    for risk_class, group in materiality.groupby("broad_risk_class"):
        ordered = group.sort_values("mean_absolute_daily_pnl_inr", ascending=False).copy()
        total = ordered["mean_absolute_daily_pnl_inr"].sum()
        ordered["cumulative_materiality_share"] = ordered["mean_absolute_daily_pnl_inr"].cumsum() / total if total else 1.0
        ordered["included_in_reduced_set"] = ordered["cumulative_materiality_share"].shift(fill_value=0.0) < target
        ordered.loc[ordered.index[0], "included_in_reduced_set"] = True
        ordered["selection_reason"] = np.where(
            ordered["included_in_reduced_set"],
            "Included in descending materiality order to represent the risk class",
            "Excluded after the configured materiality target was reached",
        )
        rows.append(ordered)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def calculate_es_and_imcc(
    factor_pnl: pd.DataFrame,
    inventory: pd.DataFrame,
    rfet: pd.DataFrame,
) -> Dict[str, Any]:
    params = load_ima_parameters()["expected_shortfall"]
    confidence = float(params["confidence_level"])
    mrf = set(rfet.loc[rfet["modellability_status"] == "MRF", "risk_factor_id"])
    current = factor_pnl[factor_pnl.date >= pd.Timestamp(factor_pnl.date.max()) - pd.offsets.BDay(int(params["current_window_business_days"]) - 1)]
    reduced_selection = select_reduced_factors(current, rfet, load_synthetic_assumptions()["history"]["reduced_materiality_target"])
    if reduced_selection.empty:
        reduced_selection = pd.DataFrame(columns=["risk_factor_id", "included_in_reduced_set"])
    reduced = set(reduced_selection.loc[reduced_selection["included_in_reduced_set"], "risk_factor_id"])
    dates = pd.DatetimeIndex(sorted(pd.to_datetime(factor_pnl["date"]).unique()))
    current_dates = dates[-int(params["current_window_business_days"]):]
    if len(current_dates) < int(params["current_window_business_days"]):
        raise ValueError("ES requires a complete current observation window")
    # Expand rather than silently accepting a reduced set that misses the coverage floor.
    for scope in [None, *params["broad_risk_classes"]]:
        full = mrf if scope is None else set(inventory.loc[inventory.broad_risk_class == scope, "risk_factor_id"]) & mrf
        full_es = liquidity_horizon_es(current, inventory, full, confidence).liquidity_horizon_adjusted_es
        red_es = liquidity_horizon_es(current, inventory, full & reduced, confidence).liquidity_horizon_adjusted_es
        if full_es and red_es / full_es < params["reduced_set_minimum_coverage"]:
            reduced |= full
    reduced_selection["included_in_reduced_set"] = reduced_selection.risk_factor_id.isin(reduced)
    stress_start, stress_end, stress_scan = _select_stress_window(factor_pnl, inventory, reduced, confidence, int(params["stress_window_business_days"]))
    period_frames = {
        "CURRENT": factor_pnl[factor_pnl["date"].isin(current_dates)],
        "STRESS": factor_pnl[(factor_pnl["date"] >= stress_start) & (factor_pnl["date"] <= stress_end)],
    }
    scopes = {"ALL": mrf}
    factor_class = inventory.set_index("risk_factor_id")["broad_risk_class"].to_dict()
    for risk_class in params["broad_risk_classes"]:
        scopes[risk_class] = {factor for factor in mrf if factor_class.get(factor) == risk_class}
    rows, component_rows, capital_rows = [], [], []
    for scope, full_factors in scopes.items():
        reduced_factors = full_factors & reduced
        values: dict[tuple[str, str], ESResult] = {}
        for period, period_frame in period_frames.items():
            for factor_set, factors in (("FULL", full_factors), ("REDUCED", reduced_factors)):
                result = liquidity_horizon_es(period_frame, inventory, factors, confidence)
                values[(period, factor_set)] = result
                rows.append({
                    "scope": scope, "period": period, "factor_set": factor_set,
                    "factor_count": len(factors), "es_10_day_inr": result.es_10_day,
                    "liquidity_horizon_adjusted_es_inr": result.liquidity_horizon_adjusted_es,
                    "period_start": str(pd.Timestamp(period_frame["date"].min()).date()),
                    "period_end": str(pd.Timestamp(period_frame["date"].max()).date()),
                })
                for component in result.components:
                    component_rows.append({"scope": scope, "period": period, "factor_set": factor_set, **component})
        full_current = values[("CURRENT", "FULL")].liquidity_horizon_adjusted_es
        reduced_current = values[("CURRENT", "REDUCED")].liquidity_horizon_adjusted_es
        reduced_stress = values[("STRESS", "REDUCED")].liquidity_horizon_adjusted_es
        coverage = reduced_current / full_current if full_current else 1.0
        ratio = max(full_current / reduced_current, float(params["stress_scaling_ratio_floor"])) if reduced_current else 1.0
        if coverage + 1e-12 < params["reduced_set_minimum_coverage"]:
            raise ValueError(f"Reduced-factor ES coverage failed for {scope}")
        scaled = reduced_stress * ratio
        capital_rows.append({
            "scope": scope, "full_current_es_inr": full_current,
            "reduced_current_es_inr": reduced_current, "reduced_stress_es_inr": reduced_stress,
            "reduced_set_coverage": coverage, "stress_scaling_ratio": ratio,
            "scaled_es_capital_inr": scaled,
            "coverage_requirement": float(params["reduced_set_minimum_coverage"]),
            "coverage_pass": coverage >= float(params["reduced_set_minimum_coverage"]),
        })
    capital = pd.DataFrame(capital_rows)
    unconstrained = float(capital.loc[capital["scope"] == "ALL", "scaled_es_capital_inr"].iloc[0])
    constrained = float(capital.loc[capital["scope"] != "ALL", "scaled_es_capital_inr"].sum())
    imcc = float(params["imcc_unconstrained_weight"]) * unconstrained + float(params["imcc_constrained_weight"]) * constrained
    return {
        "reduced_selection": reduced_selection,
        "es_summary": pd.DataFrame(rows),
        "lh_components": pd.DataFrame(component_rows),
        "scaled_es": capital,
        "stress_scan": stress_scan,
        "stress_start": stress_start,
        "stress_end": stress_end,
        "unconstrained_imcc_inr": unconstrained,
        "constrained_imcc_inr": constrained,
        "imcc_inr": imcc,
    }


def _select_stress_window(
    factor_pnl: pd.DataFrame,
    inventory: pd.DataFrame,
    reduced: set[str],
    confidence: float,
    window: int,
) -> tuple[pd.Timestamp, pd.Timestamp, pd.DataFrame]:
    dates = pd.DatetimeIndex(sorted(pd.to_datetime(factor_pnl["date"]).unique()))
    if len(dates) < window:
        raise ValueError("Insufficient dates for stress calibration")
    values = factor_pnl.pivot_table(index="date", columns="risk_factor_id", values="factor_pnl_inr", aggfunc="sum").reindex(dates).fillna(0.0)
    horizons = inventory.set_index("risk_factor_id").liquidity_horizon_days.to_dict()
    squared = np.zeros(len(dates) - window + 1)
    previous = 0
    for lh in [10, 20, 40, 60, 120]:
        factors = [f for f in values if f in reduced and horizons[f] >= lh]
        daily = values[factors].sum(axis=1)
        rolling = daily.rolling(10).sum().dropna().to_numpy()
        windows = np.lib.stride_tricks.sliding_window_view(-rolling, window - 9)
        thresholds = np.quantile(windows, confidence, axis=1)
        tail = windows >= thresholds[:, None]
        es = np.maximum((windows * tail).sum(axis=1) / tail.sum(axis=1), 0)
        squared += es**2 * (lh - previous) / 10
        previous = lh
    scan = pd.DataFrame({"window_start": dates[:len(squared)], "window_end": dates[window-1:], "reduced_lh_adjusted_es_inr": np.sqrt(squared)}).sort_values("reduced_lh_adjusted_es_inr", ascending=False).reset_index(drop=True)
    selected = scan.iloc[0]
    return pd.Timestamp(selected["window_start"]), pd.Timestamp(selected["window_end"]), scan


def calculate_nmrf_ses(
    factor_pnl: pd.DataFrame,
    inventory: pd.DataFrame,
    rfet: pd.DataFrame,
) -> Dict[str, Any]:
    params = load_ima_parameters()["nmrf"]
    nmrf = set(rfet.loc[rfet["modellability_status"] == "NMRF", "risk_factor_id"])
    merged = factor_pnl[factor_pnl["risk_factor_id"].isin(nmrf)].merge(
        inventory[["risk_factor_id", "broad_risk_class", "liquidity_horizon_days"]],
        on=["risk_factor_id", "broad_risk_class", "liquidity_horizon_days"], how="left",
    )
    rows = []
    for factor, group in merged.groupby("risk_factor_id"):
        horizon = max(int(group["liquidity_horizon_days"].iloc[0]), 20)
        daily = group.groupby("date")["factor_pnl_inr"].sum().sort_index()
        horizon_pnl = daily.rolling(horizon).sum().dropna()
        width = int(load_ima_parameters()["expected_shortfall"]["stress_window_business_days"])
        if len(daily) < width:
            raise ValueError("NMRF stress calibration requires a full annual window")
        losses = -horizon_pnl.to_numpy()
        windows = np.lib.stride_tricks.sliding_window_view(losses, width - horizon + 1)
        quantiles = np.quantile(windows, params["confidence_level"], axis=1)
        daily_values = daily.to_numpy()
        daily_windows = np.lib.stride_tricks.sliding_window_view(daily_values, width)
        parametric_losses = (
            -daily_windows.mean(axis=1) * horizon
            + t.ppf(params["confidence_level"], df=6)
            * daily_windows.std(axis=1, ddof=1) * np.sqrt(horizon)
        )
        candidate_losses = np.maximum(quantiles, parametric_losses)
        start = int(np.argmax(candidate_losses))
        stressed_daily = daily.iloc[start:start+width]
        empirical = float(quantiles[start])
        parametric = float(parametric_losses[start])
        stress_loss = max(empirical, parametric, 0.0)
        risk_class = group["broad_risk_class"].iloc[0]
        category = "OTHER_NMRF"  # No separate proof of an idiosyncratic-only component.
        window_horizon_pnl = horizon_pnl[
            (horizon_pnl.index >= stressed_daily.index[0])
            & (horizon_pnl.index <= stressed_daily.index[-1])
        ]
        worst_end = window_horizon_pnl.idxmin()
        rows.append({
            "risk_factor_id": factor, "broad_risk_class": risk_class,
            "ses_category": category, "liquidity_horizon_days": horizon,
            "empirical_stress_loss_inr": empirical, "parametric_stress_loss_inr": parametric,
            "stress_scenario_loss_inr": stress_loss,
            "worst_scenario_end_date": str(pd.Timestamp(worst_end).date()),
            "stress_window_start": str(stressed_daily.index[0].date()),
            "stress_window_end": str(stressed_daily.index[-1].date()),
            "calibration_method": "Worst rolling annual window; maximum empirical quantile and Student-t loss",
            "input_data_status": "SYNTHETIC_REGIME_AWARE",
        })
    detail = pd.DataFrame(rows, columns=["risk_factor_id", "broad_risk_class", "ses_category", "liquidity_horizon_days", "empirical_stress_loss_inr", "parametric_stress_loss_inr", "stress_scenario_loss_inr", "worst_scenario_end_date", "stress_window_start", "stress_window_end", "calibration_method", "input_data_status"])
    idio_credit = detail.loc[detail["ses_category"] == "IDIOSYNCRATIC_CREDIT", "stress_scenario_loss_inr"].to_numpy()
    idio_equity = detail.loc[detail["ses_category"] == "IDIOSYNCRATIC_EQUITY", "stress_scenario_loss_inr"].to_numpy()
    other = detail.loc[detail["ses_category"] == "OTHER_NMRF", "stress_scenario_loss_inr"].to_numpy()
    rho = float(params["other_correlation"])
    other_aggregate = float(np.sqrt((rho * other.sum()) ** 2 + (1 - rho ** 2) * np.square(other).sum())) if len(other) else 0.0
    components = {
        "idiosyncratic_credit_inr": float(np.sqrt(np.square(idio_credit).sum())),
        "idiosyncratic_equity_inr": float(np.sqrt(np.square(idio_equity).sum())),
        "other_nmrf_inr": other_aggregate,
    }
    components["ses_inr"] = sum(components.values())
    return {"detail": detail, "summary": pd.DataFrame([components]), **components}


def calculate_ima_drc(
    trades: pd.DataFrame,
    market: Dict[str, Any],
    portfolio_history: pd.DataFrame | None = None,
) -> Dict[str, Any]:
    params = load_ima_parameters()["ima_drc"]
    assumptions = load_synthetic_assumptions()["default_model"]
    rating_pd = assumptions["rating_pd"]
    valuations = _price_book(trades, market)
    sa_drc = calculate_drc(trades, valuations, market)
    gross = sa_drc["gross_jtd"].merge(
        trades[["trade_id", "sector", "economy"]], on="trade_id", how="left"
    )
    issuer = gross.groupby(["obligor", "rating", "sector", "economy"], as_index=False)["gross_jtd"].sum()
    issuer = issuer[issuer["obligor"] != "NONE"].copy()
    issuer["pd_raw"] = issuer["rating"].map(rating_pd).fillna(rating_pd["UNRATED"])
    issuer["pd"] = issuer["pd_raw"].clip(lower=float(params["probability_of_default_floor"]))
    issuer["default_threshold"] = norm.ppf(issuer["pd"])
    issuer["lgd"] = 0.75
    issuer["exposure_jtd_inr"] = issuer["gross_jtd"]
    issuer["systematic_group"] = issuer["economy"] + "|" + issuer["sector"]
    issuer["global_loading"] = float(assumptions["global_loading"])
    issuer["sector_region_loading"] = float(assumptions["sector_region_loading"])
    issuer["idiosyncratic_loading"] = np.sqrt(1 - issuer["global_loading"] ** 2 - issuer["sector_region_loading"] ** 2)

    n_sims = int(assumptions["simulation_count"])
    rng = np.random.default_rng(int(assumptions["random_seed"]))
    global_factor = rng.standard_normal(n_sims)
    groups = sorted(issuer["systematic_group"].unique())
    group_factors = {group: rng.standard_normal(n_sims) for group in groups}
    loss = np.zeros(n_sims)
    default_matrix = np.zeros((n_sims, len(issuer)), dtype=bool)
    for column, (_, row) in enumerate(issuer.reset_index(drop=True).iterrows()):
        latent = (
            row["global_loading"] * global_factor
            + row["sector_region_loading"] * group_factors[row["systematic_group"]]
            + row["idiosyncratic_loading"] * rng.standard_normal(n_sims)
        )
        defaulted = latent < row["default_threshold"]
        default_matrix[:, column] = defaulted
        loss += defaulted * float(row["exposure_jtd_inr"])
    confidence = float(params["confidence_level"])
    var = float(np.quantile(loss, confidence, method="higher"))
    tail_indices = np.where(loss >= var)[0]
    trace_rows = []
    issuer_reset = issuer.reset_index(drop=True)
    for simulation in tail_indices[:200]:
        defaulted_issuers = issuer_reset.loc[default_matrix[simulation], "obligor"].tolist()
        trace_rows.append({
            "simulation_id": int(simulation), "portfolio_default_loss_inr": float(loss[simulation]),
            "defaulted_issuer_count": len(defaulted_issuers),
            "defaulted_issuers": ", ".join(defaulted_issuers) if defaulted_issuers else "None",
        })
    distribution = pd.DataFrame({
        "loss_band_inr": np.linspace(float(loss.min()), float(loss.max()), 101)[:-1],
        "simulation_count": np.histogram(loss, bins=100)[0],
    })
    gross_by_trade = gross[["trade_id", "obligor", "gross_jtd"]].copy()
    if portfolio_history is None or portfolio_history.empty:
        week_dates = pd.date_range(end=pd.Timestamp(market["valuation_date"]), periods=12, freq="W-TUE")
        weekly = pd.DataFrame({"week": week_dates, "ima_drc_inr": var})
        weekly["history_basis"] = "Current portfolio held constant across the retained weekly dates"
    else:
        snapshots = portfolio_history.copy()
        snapshots["date"] = pd.to_datetime(snapshots["date"])
        available = pd.DatetimeIndex(sorted(snapshots["date"].unique()))
        week_dates = available.to_series().groupby(available.to_period("W-TUE")).max().tail(12).to_list()
        weekly_rows = []
        issuer_order = issuer["obligor"].to_list()
        for week_date in week_dates:
            scales = snapshots[snapshots["date"] == week_date][["trade_id", "position_multiplier"]]
            dated = gross_by_trade.merge(scales, on="trade_id", how="left")
            dated["position_multiplier"] = dated["position_multiplier"].fillna(1.0)
            exposures = (dated["gross_jtd"] * dated["position_multiplier"]).groupby(dated["obligor"]).sum()
            vector = np.array([float(exposures.get(name, 0.0)) for name in issuer_order])
            dated_loss = default_matrix @ vector
            weekly_rows.append({
                "week": week_date,
                "ima_drc_inr": float(np.quantile(dated_loss, confidence, method="higher")),
                "history_basis": "Dated synthetic position snapshot with the same calibrated default scenarios",
            })
        weekly = pd.DataFrame(weekly_rows)
    capital = max(var, float(weekly["ima_drc_inr"].mean()))
    return {
        "issuer_inputs": issuer,
        "loss_distribution": distribution,
        "tail_trace": pd.DataFrame(trace_rows),
        "weekly_history": weekly,
        "current_drc_inr": var,
        "average_12_week_drc_inr": float(weekly["ima_drc_inr"].mean()),
        "ima_drc_capital_inr": capital,
        "simulation_count": n_sims,
    }


def generate_portfolio_history(
    trades: pd.DataFrame,
    dates: Iterable[pd.Timestamp],
    seed: int = 20260827,
) -> pd.DataFrame:
    """Create reproducible daily position snapshots with economically limited changes."""
    dates = pd.DatetimeIndex(sorted(pd.to_datetime(list(dates))))
    rng = np.random.default_rng(seed)
    rows = []
    for _, trade in trades.iterrows():
        multiplier = 1.0
        resize_offset = int(rng.integers(8, 55))
        hedge_offset = int(rng.integers(10, 85))
        for index, date in enumerate(dates):
            event = "UNCHANGED"
            if index > 0 and index % 63 == resize_offset:
                multiplier *= float(rng.choice([0.80, 0.90, 1.10, 1.20]))
                event = "POSITION_RESIZED"
            if index > 0 and index % 97 == hedge_offset and trade["product_form"] == "derivative":
                multiplier *= 0.90
                event = "HEDGE_ADJUSTED"
            if index == len(dates) - 1:
                multiplier = 1.0
                event = "CURRENT_BOOK_ANCHOR"
            rows.append({
                "date": date, "trade_id": trade["trade_id"], "desk": trade["desk"],
                "instrument_type": trade["instrument_type"], "position_multiplier": multiplier,
                "position_event": event, "notional_or_quantity_scale": multiplier,
                "data_status": "SYNTHETIC_SYSTEMATIC_PORTFOLIO_HISTORY",
            })
    return pd.DataFrame(rows)


def calculate_daily_pnl_and_pla(
    history: pd.DataFrame,
    exposures: pd.DataFrame,
    inventory: pd.DataFrame,
    rfet: pd.DataFrame,
    portfolio_history: pd.DataFrame,
    trades: pd.DataFrame,
    market: Dict[str, Any],
) -> Dict[str, pd.DataFrame]:
    """Calculate HPL, RTPL, APL and PLA from one frozen-position history."""
    from frtb_engine.scenarios import daily_repricing
    daily, detail = daily_repricing(
        history, exposures, inventory, trades, market, portfolio_history, rfet
    )
    daily = daily.sort_values(["desk", "date"]).reset_index(drop=True)

    pla_rows = []
    for desk, group in daily.groupby("desk"):
        sample = group.tail(250).dropna(subset=["hpl_inr", "rtpl_inr"])
        if len(sample) < 250:
            spearman, ks, zone = float("nan"), float("nan"), "RED"
            reason = "Fewer than 250 complete daily observations are available"
            pla_rows.append({
                "desk": desk, "observations": len(sample), "spearman_correlation": spearman,
                "ks_statistic": ks, "pla_zone": zone, "pla_reason": reason,
            })
            continue
        spearman = float(spearmanr(sample["hpl_inr"], sample["rtpl_inr"]).statistic)
        ks = float(ks_2samp(sample["hpl_inr"], sample["rtpl_inr"]).statistic)
        if spearman > 0.80 and ks < 0.09:
            zone = "GREEN"
            reason = "Both Spearman and KS metrics satisfy the green-zone thresholds"
        elif spearman < 0.70 or ks > 0.12:
            zone = "RED"
            reason = "At least one metric breaches a red-zone threshold"
        else:
            zone = "AMBER"
            reason = "Metrics fall between the green and red thresholds"
        pla_rows.append({
            "desk": desk, "observations": len(sample), "spearman_correlation": spearman,
            "ks_statistic": ks, "pla_zone": zone, "pla_reason": reason,
        })
    return {"daily_pnl": daily, "trade_pnl_detail": detail, "pla": pd.DataFrame(pla_rows)}


def calculate_backtesting(daily_pnl: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    rows = []
    for desk, group in daily_pnl.groupby("desk"):
        group = group.sort_values("date").reset_index(drop=True)
        for index in range(250, len(group)):
            history = group.iloc[index - 250:index]
            outcome = group.iloc[index]
            var_975 = max(float(-np.quantile(history["hpl_inr"], 0.025)), 0.0)
            var_99 = max(float(-np.quantile(history["hpl_inr"], 0.01)), 0.0)
            rows.append({
                "desk": desk, "forecast_date": group.iloc[index - 1]["date"],
                "outcome_date": outcome["date"], "var_97_5_inr": var_975, "var_99_inr": var_99,
                "next_day_hpl_inr": outcome["hpl_inr"], "next_day_apl_inr": outcome["apl_inr"],
                "hpl_exception_97_5": bool(-outcome["hpl_inr"] > var_975),
                "hpl_exception_99": bool(-outcome["hpl_inr"] > var_99),
                "apl_exception_97_5": bool(-outcome["apl_inr"] > var_975),
                "apl_exception_99": bool(-outcome["apl_inr"] > var_99),
                "forecast_information": "Only the preceding 250 observations",
            })
    detail = pd.DataFrame(rows)
    summaries = []
    for desk, group in detail.groupby("desk"):
        hpl975 = int(group["hpl_exception_97_5"].sum())
        hpl99 = int(group["hpl_exception_99"].sum())
        apl975 = int(group["apl_exception_97_5"].sum())
        apl99 = int(group["apl_exception_99"].sum())
        e975, e99 = max(hpl975, apl975), max(hpl99, apl99)
        pass_result = len(group) == 250 and e975 <= 30 and e99 <= 12
        summaries.append({
            "desk": desk, "observations": len(group), "hpl_exceptions_97_5": hpl975,
            "hpl_exceptions_99": hpl99, "apl_exceptions_97_5": apl975,
            "apl_exceptions_99": apl99, "exceptions_used_97_5": e975,
            "exceptions_used_99": e99,
            "backtesting_result": "PASS" if pass_result else "FAIL",
            "backtesting_reason": "Exception counts are within desk thresholds" if pass_result else "A desk exception threshold was exceeded",
        })
    return {"detail": detail, "summary": pd.DataFrame(summaries)}


def determine_desk_eligibility(
    pla: pd.DataFrame,
    backtesting: pd.DataFrame,
    all_desks: Iterable[str] | None = None,
) -> pd.DataFrame:
    result = pla.merge(backtesting, on="desk", how="outer")
    if all_desks is not None:
        missing = sorted(set(all_desks) - set(result["desk"]))
        if missing:
            result = pd.concat([result, pd.DataFrame({"desk": missing})], ignore_index=True)
    result = result.rename(columns={"observations_x": "pla_observations", "observations_y": "backtesting_observations"})
    numeric_defaults = {
        "pla_observations": 0, "spearman_correlation": 0.0, "ks_statistic": 0.0,
        "backtesting_observations": 0, "hpl_exceptions_97_5": 0,
        "hpl_exceptions_99": 0, "apl_exceptions_97_5": 0,
        "apl_exceptions_99": 0, "exceptions_used_97_5": 0,
        "exceptions_used_99": 0,
    }
    for column, default in numeric_defaults.items():
        if column in result:
            result[column] = result[column].fillna(default)
    result["pla_zone"] = result["pla_zone"].fillna("NOT_APPLICABLE")
    result["pla_reason"] = result["pla_reason"].fillna("PLA is not performed for a desk outside IMA nomination")
    result["backtesting_result"] = result["backtesting_result"].fillna("NOT_APPLICABLE")
    result["backtesting_reason"] = result["backtesting_reason"].fillna("Backtesting is not performed for a desk outside IMA nomination")
    treatments, reasons = [], []
    for _, row in result.iterrows():
        if row["desk"] == "Residual Risk":
            treatment, reason = "SA_FALLBACK", "Desk is not nominated for IMA because its exotic underlyings are outside the internal model"
        elif row["backtesting_result"] != "PASS" or row["backtesting_observations"] < 250:
            treatment, reason = "SA_FALLBACK", "Desk backtesting threshold failed"
        elif row["pla_zone"] == "RED" or row["pla_observations"] < 250:
            treatment, reason = "SA_FALLBACK", "PLA red-zone result"
        elif row["pla_zone"] == "AMBER":
            treatment, reason = "IMA_AMBER", "PLA amber-zone result; IMA remains available with the applicable surcharge"
        else:
            treatment, reason = "IMA_GREEN", "PLA green-zone result and desk backtesting passed"
        treatments.append(treatment)
        reasons.append(reason)
    result["final_treatment"] = treatments
    result["eligibility_reason"] = reasons
    result["ima_eligible"] = result["final_treatment"].isin(["IMA_GREEN", "IMA_AMBER"])
    return result


def backtesting_multiplier(exception_count: int) -> float:
    table = load_ima_parameters()["bank_wide_backtesting_multiplier"]
    if exception_count >= 10:
        return float(table["10_or_more"])
    return float(table[int(exception_count)] if int(exception_count) in table else table[str(int(exception_count))])
