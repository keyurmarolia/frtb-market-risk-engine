"""Seven-risk-class sensitivities-based method aggregation."""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

import pandas as pd

from frtb_engine.parameters import (
    cross_bucket_correlation,
    is_special_bucket,
    risk_weight,
    within_bucket_correlation,
)


SCENARIOS = ["low", "medium", "high"]
RISK_CLASSES = [
    "GIRR", "CSR_NON_SECURITISATION", "CSR_SECURITISATION_NON_CTP",
    "CSR_SECURITISATION_CTP", "EQUITY", "COMMODITY", "FX",
]


def net_and_weight(sensitivities: pd.DataFrame) -> pd.DataFrame:
    if sensitivities.empty:
        return sensitivities.copy()
    sensitivities = sensitivities.copy()
    if "underlying_tenor" not in sensitivities:
        sensitivities["underlying_tenor"] = float("nan")
    keys = [
        "risk_class", "bucket", "risk_measure", "risk_factor_id", "tenor",
        "factor_type", "name", "curve", "location", "underlying_tenor",
    ]
    netted = sensitivities.groupby(keys, dropna=False, as_index=False)["raw_sensitivity"].sum()
    netted["risk_weight"] = netted.apply(
        lambda row: risk_weight(row.to_dict(), row["risk_measure"]), axis=1
    )
    netted["weighted_sensitivity"] = netted["raw_sensitivity"] * netted["risk_weight"]
    return netted


def aggregate_linear_measure(weighted: pd.DataFrame, scenario: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    bucket_rows: List[Dict] = []
    class_rows: List[Dict] = []
    for risk_class in RISK_CLASSES:
        class_data = weighted[weighted["risk_class"] == risk_class] if not weighted.empty else weighted
        if class_data.empty:
            class_rows.append({"scenario": scenario, "risk_class": risk_class, "capital": 0.0})
            continue
        for bucket, bucket_data in class_data.groupby("bucket"):
            records = bucket_data.to_dict(orient="records")
            if is_special_bucket(risk_class, str(bucket)):
                k_value = sum(abs(float(row["weighted_sensitivity"])) for row in records)
            else:
                variance = sum(float(row["weighted_sensitivity"]) ** 2 for row in records)
                for index, left in enumerate(records):
                    for right in records[index + 1:]:
                        rho = within_bucket_correlation(left, right, scenario)
                        variance += 2.0 * rho * float(left["weighted_sensitivity"]) * float(right["weighted_sensitivity"])
                k_value = math.sqrt(max(variance, 0.0))
            raw_sum = sum(float(row["weighted_sensitivity"]) for row in records)
            s_value = raw_sum
            bucket_rows.append({
                "scenario": scenario, "risk_class": risk_class, "bucket": str(bucket),
                "k_bucket": k_value, "s_bucket": s_value,
                "weighted_sensitivity_sum": raw_sum,
            })
        risk_buckets = [row for row in bucket_rows if row["scenario"] == scenario and row["risk_class"] == risk_class]
        special = [r for r in risk_buckets if is_special_bucket(risk_class, r["bucket"])]
        risk_buckets = [r for r in risk_buckets if r not in special]
        variance = sum(row["k_bucket"] ** 2 for row in risk_buckets)
        for index, left in enumerate(risk_buckets):
            for right in risk_buckets[index + 1:]:
                gamma = cross_bucket_correlation(risk_class, left["bucket"], right["bucket"], scenario)
                variance += 2.0 * gamma * left["s_bucket"] * right["s_bucket"]
        if variance < 0:
            for row in risk_buckets:
                row["s_bucket"] = max(-row["k_bucket"], min(row["s_bucket"], row["k_bucket"]))
            variance = sum(row["k_bucket"] ** 2 for row in risk_buckets)
            for i, left in enumerate(risk_buckets):
                for right in risk_buckets[i + 1:]:
                    variance += 2 * cross_bucket_correlation(risk_class, left["bucket"], right["bucket"], scenario) * left["s_bucket"] * right["s_bucket"]
        class_rows.append({"scenario": scenario, "risk_class": risk_class, "capital": math.sqrt(max(variance, 0.0)) + sum(r["k_bucket"] for r in special)})
    return pd.DataFrame(bucket_rows), pd.DataFrame(class_rows)


def aggregate_curvature(curvature: pd.DataFrame, scenario: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    bucket_rows: List[Dict] = []
    class_rows: List[Dict] = []
    if curvature.empty:
        return pd.DataFrame(), pd.DataFrame([{"scenario": scenario, "risk_class": risk_class, "capital": 0.0} for risk_class in RISK_CLASSES])
    keys = ["risk_class", "bucket", "risk_factor_id", "tenor", "factor_type", "name", "curve", "location"]
    netted = curvature.groupby(keys, dropna=False, as_index=False)[["curvature_up", "curvature_down"]].sum()
    for risk_class in RISK_CLASSES:
        class_data = netted[netted["risk_class"] == risk_class]
        if class_data.empty:
            class_rows.append({"scenario": scenario, "risk_class": risk_class, "capital": 0.0})
            continue
        for bucket, bucket_data in class_data.groupby("bucket"):
            records = bucket_data.to_dict(orient="records")
            direction_results = {}
            for direction in ["curvature_up", "curvature_down"]:
                if is_special_bucket(risk_class, str(bucket)):
                    direction_results[direction] = sum(max(float(row[direction]), 0) for row in records)
                    continue
                variance = sum(max(float(row[direction]), 0.0) ** 2 for row in records)
                for index, left in enumerate(records):
                    for right in records[index + 1:]:
                        left_value, right_value = float(left[direction]), float(right[direction])
                        psi = 0.0 if left_value < 0 and right_value < 0 else 1.0
                        rho = within_bucket_correlation(left, right, scenario, curvature=True)
                        variance += 2.0 * rho * left_value * right_value * psi
                direction_results[direction] = math.sqrt(max(variance, 0.0))
            ku, kd = direction_results["curvature_up"], direction_results["curvature_down"]
            selected = "up" if ku > kd or (ku == kd and sum(r["curvature_up"] for r in records) > sum(r["curvature_down"] for r in records)) else "down"
            column = "curvature_up" if selected == "up" else "curvature_down"
            s_value = sum(float(row[column]) for row in records)
            bucket_rows.append({
                "scenario": scenario, "risk_class": risk_class, "bucket": str(bucket),
                "k_bucket": direction_results[column], "s_bucket": s_value,
                "selected_direction": selected,
                "up_capital": direction_results["curvature_up"],
                "down_capital": direction_results["curvature_down"],
            })
        risk_buckets = [row for row in bucket_rows if row["scenario"] == scenario and row["risk_class"] == risk_class]
        special = [r for r in risk_buckets if is_special_bucket(risk_class, r["bucket"])]
        risk_buckets = [r for r in risk_buckets if r not in special]
        variance = sum(row["k_bucket"] ** 2 for row in risk_buckets)
        for index, left in enumerate(risk_buckets):
            for right in risk_buckets[index + 1:]:
                psi = 0.0 if left["s_bucket"] < 0 and right["s_bucket"] < 0 else 1.0
                gamma = cross_bucket_correlation(risk_class, left["bucket"], right["bucket"], scenario, curvature=True)
                variance += 2.0 * gamma * left["s_bucket"] * right["s_bucket"] * psi
        class_rows.append({"scenario": scenario, "risk_class": risk_class, "capital": math.sqrt(max(variance, 0.0)) + sum(r["k_bucket"] for r in special)})
    return pd.DataFrame(bucket_rows), pd.DataFrame(class_rows)


def calculate_sbm(delta: pd.DataFrame, vega: pd.DataFrame, curvature: pd.DataFrame) -> Dict[str, pd.DataFrame | float | str]:
    weighted_delta = net_and_weight(delta)
    weighted_vega = net_and_weight(vega)
    all_buckets, all_classes, summaries = [], [], []
    for scenario in SCENARIOS:
        delta_buckets, delta_classes = aggregate_linear_measure(weighted_delta, scenario)
        delta_buckets["risk_measure"] = "DELTA"
        delta_classes["risk_measure"] = "DELTA"
        vega_buckets, vega_classes = aggregate_linear_measure(weighted_vega, scenario)
        vega_buckets["risk_measure"] = "VEGA"
        vega_classes["risk_measure"] = "VEGA"
        curvature_buckets, curvature_classes = aggregate_curvature(curvature, scenario)
        curvature_buckets["risk_measure"] = "CURVATURE"
        curvature_classes["risk_measure"] = "CURVATURE"
        all_buckets.extend([delta_buckets, vega_buckets, curvature_buckets])
        all_classes.extend([delta_classes, vega_classes, curvature_classes])
        total = float(delta_classes["capital"].sum() + vega_classes["capital"].sum() + curvature_classes["capital"].sum())
        summaries.append({"scenario": scenario, "sbm_capital": total})
    scenario_summary = pd.DataFrame(summaries)
    selected_row = scenario_summary.loc[scenario_summary["sbm_capital"].idxmax()]
    return {
        "weighted_delta": weighted_delta,
        "weighted_vega": weighted_vega,
        "bucket_results": pd.concat(all_buckets, ignore_index=True),
        "class_results": pd.concat(all_classes, ignore_index=True),
        "scenario_summary": scenario_summary,
        "selected_scenario": str(selected_row["scenario"]),
        "sbm_capital": float(selected_row["sbm_capital"]),
    }
