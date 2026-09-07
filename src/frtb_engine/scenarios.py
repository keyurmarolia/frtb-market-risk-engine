"""Revalue the shared contracts under aligned synthetic market scenarios."""

from copy import deepcopy
import numpy as np
import pandas as pd

from frtb_engine.pricing import price_trade_inr
from frtb_engine.sensitivities import CSR_TENORS


def scenario_market(market, exposures, changes, selected=None):
    """Apply curve-node, spot and volatility-node changes to one trade's market.

    Spot/FX changes are proportional; rates, spreads and volatility changes
    are absolute. Vega nodes are interpolated with their allocation weights.
    """
    result = deepcopy(market)
    vol_changes = {}
    for row in exposures.to_dict("records"):
        factor = row["risk_factor_id"]
        if factor not in changes or (selected is not None and factor not in selected):
            continue
        change = np.asarray(changes[factor], dtype=float)
        group, key = row["market_group"], row["market_key"]
        if group == "volatility":
            weight = row.get("allocation_weight", 1.0)
            weight = 1.0 if pd.isna(weight) else float(weight)
            vol_changes[key] = vol_changes.get(key, 0.0) + weight * change
        elif group in {"rates", "credit_spreads"}:
            curve = result[group][key]
            if not isinstance(curve, dict):
                curve = {t: curve for t in CSR_TENORS}
                result[group][key] = curve
            tenor = min(curve, key=lambda t: abs(float(t) - float(row["tenor"])))
            curve[tenor] = curve[tenor] + change
        else:
            base = market[group][key]
            result[group][key] = base * (1 + change) if group in {"equity_spot", "commodity_spot", "fx"} else base + change
    for key, change in vol_changes.items():
        result["volatility"][key] = np.maximum(market["volatility"][key] + change, 1e-6)
    return result


def full_revaluation(trade, market, exposures, changes, selected=None):
    return price_trade_inr(trade, scenario_market(market, exposures, changes, selected)) - price_trade_inr(trade, market)


def factor_revaluations(history, exposures, inventory, trades, market):
    """Single-factor revaluation P&L, retained by trade and date.

    This additive internal model retains each factor's nonlinear price effect.
    Cross-factor interactions are measured independently by full-repricing PLA.
    """
    wide = history.pivot(index="date", columns="risk_factor_id", values="daily_change").sort_index()
    lookup = inventory.set_index("risk_factor_id")
    trade_lookup = trades.set_index("trade_id").to_dict("index")
    rows = []
    for trade_id, group in exposures.groupby("trade_id", sort=False):
        trade = {"trade_id": trade_id, **trade_lookup[trade_id]}
        for _, factor in group.iterrows():
            fid = factor["risk_factor_id"]
            move = wide[fid].to_numpy()
            pnl = full_revaluation(trade, market, group[group.risk_factor_id == fid], {fid: move})
            derivative = factor["price_vega"] if factor["ima_risk_measure"] == "VEGA" else factor["raw_sensitivity"]
            linear = derivative * move
            rows.append(pd.DataFrame({
                "date": wide.index, "trade_id": trade_id, "desk": trade["desk"],
                "risk_factor_id": fid, "broad_risk_class": factor["broad_risk_class"],
                "ima_risk_measure": factor["ima_risk_measure"], "daily_change": move,
                "raw_sensitivity": derivative, "linear_pnl_inr": linear,
                "nonlinear_pnl_inr": pnl - linear, "factor_pnl_inr": pnl,
                "liquidity_horizon_days": lookup.loc[fid, "liquidity_horizon_days"],
                "pnl_method": "Single-factor full revaluation; additive internal model",
            }))
    return pd.concat(rows, ignore_index=True)


def daily_repricing(history, exposures, inventory, trades, market, snapshots, rfet):
    """Frozen prior-day positions, joint market moves and an additive risk model."""
    changes = history.pivot(index="date", columns="risk_factor_id", values="daily_change").sort_index()
    dates = pd.DatetimeIndex(sorted(pd.to_datetime(snapshots.date.unique())))
    changes = changes.reindex(dates)
    mrf = set(rfet.loc[rfet.modellability_status == "MRF", "risk_factor_id"])
    rows = []
    for trade in trades.to_dict("records"):
        group = exposures[exposures.trade_id == trade["trade_id"]]
        if group.empty:
            continue
        path = snapshots[snapshots.trade_id == trade["trade_id"]].set_index("date").reindex(dates)
        holdings = path.position_multiplier.shift(1)
        full = full_revaluation(trade, market, group, changes)
        model = np.zeros(len(dates))
        for fid in group.risk_factor_id.unique():
            if fid in mrf:
                model += full_revaluation(trade, market, group[group.risk_factor_id == fid], changes, {fid})
        # Synthetic execution cost depends on turnover, not a designed PLA grade.
        turnover = path.position_multiplier.diff().abs()
        base_value = abs(float(price_trade_inr(trade, market)))
        gross = max(base_value, abs(float(trade["notional"])) * 0.01)
        fees = turnover * gross * 0.0001
        rows.append(pd.DataFrame({"date": dates, "trade_id": trade["trade_id"], "desk": trade["desk"],
                                  "prior_day_position_multiplier": holdings,
                                  "hpl_inr": full * holdings, "rtpl_inr": model * holdings,
                                  "apl_inr": full * holdings - fees,
                                  "synthetic_execution_cost_inr": fees}))
    detail = pd.concat(rows, ignore_index=True).dropna()
    daily = detail.groupby(["date", "desk"], as_index=False)[["hpl_inr", "rtpl_inr", "apl_inr"]].sum()
    daily["data_status"] = "SYNTHETIC_DAILY_PNL"
    daily["hpl_definition"] = "Prior-day trade positions; joint scenario revaluation of constant-tenor contracts"
    daily["rtpl_definition"] = "Same positions; additive single-factor revaluation over modellable factors"
    return daily, detail
