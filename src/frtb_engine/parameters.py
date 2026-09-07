"""Versioned Basel parameter access and correlation rules."""

from __future__ import annotations

import math
from typing import Any, Dict

from frtb_engine.config import load_sbm_parameters


def risk_weight(factor: Dict[str, Any], risk_measure: str) -> float:
    params = load_sbm_parameters()
    risk_class = factor["risk_class"]
    bucket = int(float(factor["bucket"])) if risk_class != "GIRR" and risk_class != "FX" else factor["bucket"]
    if risk_measure == "VEGA":
        if risk_class == "EQUITY":
            equity_bucket = int(float(factor["bucket"]))
            key = "EQUITY_LARGE_AND_INDEX" if equity_bucket in set(range(1, 9)) | {12, 13} else "EQUITY_SMALL_AND_OTHER"
            return float(params["vega_risk_weights"][key])
        return float(params["vega_risk_weights"][risk_class])
    delta = params["delta_risk_weights"][risk_class]
    if risk_class == "GIRR":
        factor_type = factor.get("factor_type", "standard")
        if factor_type == "inflation":
            return float(delta["inflation"])
        if factor_type == "cross_currency_basis":
            return float(delta["cross_currency_basis"])
        tenor = nearest_parameter_tenor(float(factor["tenor"]), delta["tenors"])
        return float(delta["tenors"][tenor])
    if risk_class == "CSR_SECURITISATION_NON_CTP":
        b = int(bucket)
        if b == 25:
            return float(delta["other_bucket_25"])
        base_bucket = ((b - 1) % 8) + 1
        base = float(delta["base_buckets_1_to_8"][base_bucket])
        if 9 <= b <= 16:
            return base * float(delta["non_senior_ig_multiplier"])
        if 17 <= b <= 24:
            return base * float(delta["high_yield_multiplier"])
        return base
    if risk_class == "EQUITY":
        return float(delta["spot_buckets"][int(bucket)])
    if risk_class == "FX":
        return float(delta["all_pairs"])
    return float(delta["buckets"][int(bucket)])


def nearest_parameter_tenor(tenor: float, mapping: Dict[Any, Any]) -> Any:
    return min(mapping, key=lambda key: abs(float(key) - tenor))


def scenario_correlation(base: float, scenario: str) -> float:
    if scenario == "medium":
        return base
    if scenario == "high":
        return min(1.25 * base, 1.0)
    if scenario == "low":
        return max(2.0 * base - 1.0, 0.75 * base)
    raise ValueError(f"Unknown correlation scenario: {scenario}")


def within_bucket_correlation(left: Dict[str, Any], right: Dict[str, Any], scenario: str, curvature: bool = False) -> float:
    if left["risk_factor_id"] == right["risk_factor_id"]:
        return 1.0
    params = load_sbm_parameters()
    risk_class = left["risk_class"]
    if risk_class == "GIRR":
        factor_types = {left.get("factor_type", "standard"), right.get("factor_type", "standard")}
        if "cross_currency_basis" in factor_types:
            base = 0.0
        elif factor_types == {"inflation", "standard"}:
            base = 0.40
        elif factor_types == {"inflation"}:
            base = 0.999
        else:
            left_t = _safe_tenor(left.get("tenor"))
            right_t = _safe_tenor(right.get("tenor"))
            base = max(math.exp(-0.03 * abs(left_t - right_t) / min(left_t, right_t)), 0.40)
            if left.get("curve") != right.get("curve"):
                base *= 0.999
    elif risk_class in {"CSR_NON_SECURITISATION", "CSR_SECURITISATION_CTP"}:
        rules = params["within_bucket_base_correlations"][risk_class]
        base = (1.0 if left["name"] == right["name"] else float(rules["different_name"]))
        base *= 1.0 if left.get("tenor") == right.get("tenor") else float(rules["different_tenor"])
        base *= 1.0 if left.get("curve") == right.get("curve") else float(rules["different_curve"])
    elif risk_class == "CSR_SECURITISATION_NON_CTP":
        rules = params["within_bucket_base_correlations"][risk_class]
        base = 1.0 if left["name"] == right["name"] else float(rules["different_tranche"])
        base *= 1.0 if left.get("tenor") == right.get("tenor") else float(rules["different_tenor"])
        base *= 1.0 if left.get("curve") == right.get("curve") else float(rules["different_curve"])
    elif risk_class == "EQUITY":
        base = float(params["within_bucket_base_correlations"]["EQUITY"].get(int(float(left["bucket"])), 0.0))
    elif risk_class == "COMMODITY":
        rules = params["within_bucket_base_correlations"]["COMMODITY"]
        base = 1.0 if left["name"] == right["name"] else float(rules[int(float(left["bucket"]))])
        base *= 1.0 if left.get("tenor") == right.get("tenor") else 0.99
        base *= 1.0 if left.get("location") == right.get("location") else 0.999
    else:
        base = 1.0
    if curvature:
        if risk_class == "GIRR":
            base = 1.0 if left.get("curve") == right.get("curve") else 0.999
        elif risk_class.startswith("CSR"):
            rules = params["within_bucket_base_correlations"][risk_class]
            base = 1.0 if left["name"] == right["name"] else float(rules.get("different_name", rules.get("different_tranche", 0.0)))
        elif risk_class == "COMMODITY":
            base = 1.0 if left["name"] == right["name"] else float(params["within_bucket_base_correlations"]["COMMODITY"][int(float(left["bucket"]))])
    if left.get("risk_measure") == "VEGA" and right.get("risk_measure") == "VEGA":
        left_t = max(_safe_tenor(left.get("tenor"), 0.5), 0.25)
        right_t = max(_safe_tenor(right.get("tenor"), 0.5), 0.25)
        if risk_class == "GIRR":
            u, v = _safe_tenor(left.get("underlying_tenor")), _safe_tenor(right.get("underlying_tenor"))
            base = math.exp(-0.01 * abs(u-v) / min(u, v))
        elif risk_class.startswith("CSR"):
            rules = params["within_bucket_base_correlations"][risk_class]
            base = 1.0 if left["name"] == right["name"] else float(rules.get("different_name", rules.get("different_tranche", 0.0)))
        elif risk_class == "EQUITY" and left["name"] == right["name"]:
            base = 1.0
        elif risk_class == "COMMODITY":
            base = 1.0 if left["name"] == right["name"] else float(params["within_bucket_base_correlations"]["COMMODITY"][int(float(left["bucket"]))])
        base *= math.exp(-0.01 * abs(left_t - right_t) / min(left_t, right_t))
    return scenario_correlation(base**2 if curvature else base, scenario)


def _safe_tenor(value: Any, default: float = 1.0) -> float:
    if value is None:
        return default
    numeric = float(value)
    return default if math.isnan(numeric) else numeric


def cross_bucket_correlation(risk_class: str, left_bucket: str, right_bucket: str, scenario: str, curvature: bool = False) -> float:
    params = load_sbm_parameters()
    left = int(float(left_bucket)) if risk_class not in {"GIRR", "FX"} else left_bucket
    right = int(float(right_bucket)) if risk_class not in {"GIRR", "FX"} else right_bucket
    if risk_class in {"CSR_NON_SECURITISATION", "CSR_SECURITISATION_CTP"}:
        base = csr_cross_bucket_correlation(int(left), int(right))
    elif risk_class == "EQUITY":
        if 11 in {left, right}:
            base = 0.0
        elif {left, right} == {12, 13}:
            base = 0.75
        elif left <= 10 and right <= 10:
            base = 0.15
        else:
            base = 0.45
    elif risk_class == "COMMODITY":
        base = 0.0 if 11 in {left, right} else 0.20
    else:
        base = float(params["cross_bucket_correlations"][risk_class])
    return scenario_correlation(base**2 if curvature else base, scenario)


def csr_cross_bucket_correlation(left: int, right: int) -> float:
    if 16 in {left, right}:
        return 0.0
    if {left, right} == {17, 18}:
        return 0.75
    if left in {17, 18} or right in {17, 18}:
        return 0.45
    left_sector = left if left <= 8 else left - 8
    right_sector = right if right <= 8 else right - 8
    if left_sector == right_sector:
        sector = 1.0
    else:
        pair = tuple(sorted((left_sector, right_sector)))
        sector_matrix = {
            (1, 2): .10, (1, 3): .20, (1, 4): .25, (1, 5): .20, (1, 6): .15, (1, 7): .10, (1, 8): 0.0,
            (2, 3): .05, (2, 4): .15, (2, 5): .20, (2, 6): .15, (2, 7): .10, (2, 8): .10,
            (3, 4): .05, (3, 5): .15, (3, 6): .20, (3, 7): .05, (3, 8): .20,
            (4, 5): .20, (4, 6): .25, (4, 7): .05, (4, 8): .05,
            (5, 6): .25, (5, 7): .05, (5, 8): .15,
            (6, 7): .05, (6, 8): .20, (7, 8): .05,
        }
        sector = sector_matrix.get(pair, 0.0)
    different_rating = (left <= 8) != (right <= 8)
    return sector * (0.5 if different_rating else 1.0)


def is_special_bucket(risk_class: str, bucket: str) -> bool:
    params = load_sbm_parameters()
    values = params["special_buckets"].get(risk_class, [])
    if not values:
        return False
    return int(float(bucket)) in {int(value) for value in values}
