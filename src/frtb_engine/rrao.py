"""Residual risk add-on based on gross notional with no netting."""

from __future__ import annotations

from typing import Dict

import pandas as pd

from frtb_engine.config import load_market_data, load_rrao_parameters


def calculate_rrao(trades: pd.DataFrame, market=None) -> Dict[str, pd.DataFrame | float]:
    params = load_rrao_parameters()
    market = load_market_data() if market is None else market
    rows = []
    candidates = trades[trades["rrao_type"] != "NONE"]
    for trade in candidates.to_dict(orient="records"):
        risk_type = trade["rrao_type"]
        fx = 1.0 if trade["currency"] == "INR" else float(market["fx"][f"{trade['currency']}INR"])
        gross_notional_inr = abs(float(trade["notional"])) * fx
        if trade["instrument_type"] == "BARRIER_OPTION":
            gross_notional_inr = abs(float(trade["quantity"])) * float(market["equity_spot"][trade["underlying"]]) * fx
        elif trade["instrument_type"] == "FX_OPTION":
            gross_notional_inr = abs(float(trade["notional"])) * float(market["fx"][trade["underlying"]])
        rw = float(params["risk_weights"][risk_type])
        rows.append({
            "trade_id": trade["trade_id"], "desk": trade["desk"],
            "instrument_type": trade["instrument_type"], "rrao_type": risk_type,
            "classification_reason": trade["rrao_reason"],
            "gross_notional_inr": gross_notional_inr, "risk_weight": rw,
            "rrao_charge": gross_notional_inr * rw,
            "netting_allowed": False, "additional_to_sbm_and_drc": True,
        })
    detail = pd.DataFrame(rows)
    total = float(detail["rrao_charge"].sum()) if not detail.empty else 0.0
    return {"detail": detail, "rrao_capital": total}
