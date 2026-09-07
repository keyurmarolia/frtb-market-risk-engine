"""Build the portable Excel reporting layer from the latest completed IMA run."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import xlsxwriter
import yaml


ROOT = Path(__file__).resolve().parents[1]
INR_CRORE = 10_000_000


def _latest_run() -> tuple[Path, dict]:
    run_id = (ROOT / "outputs/latest_ima_run.txt").read_text(encoding="utf-8").strip()
    run = ROOT / "outputs" / run_id
    summary = json.loads((run / "27_combined_capital_summary.json").read_text(encoding="utf-8"))
    return run, summary


def _read(run: Path, stage: str) -> pd.DataFrame:
    candidates = [run / f"{stage}.csv", run / f"{stage}.csv.gz"]
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        raise FileNotFoundError(f"Missing report input: {stage}")
    return pd.read_csv(path, keep_default_na=False)


def _formats(workbook: xlsxwriter.Workbook) -> dict:
    return {
        "title": workbook.add_format({"bold": True, "font_size": 20, "font_color": "#FFFFFF", "bg_color": "#17365D", "align": "left", "valign": "vcenter"}),
        "section": workbook.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#17365D", "align": "left"}),
        "header": workbook.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#4472C4", "border": 0, "align": "center", "valign": "vcenter", "text_wrap": True}),
        "label": workbook.add_format({"font_color": "#000000", "align": "left"}),
        "linked": workbook.add_format({"font_color": "#008000", "num_format": "#,##0.00;[Red](#,##0.00);-"}),
        "formula": workbook.add_format({"font_color": "#000000", "num_format": "#,##0.00;[Red](#,##0.00);-"}),
        "crore": workbook.add_format({"font_color": "#000000", "num_format": "#,##0.00;[Red](#,##0.00);-"}),
        "percent": workbook.add_format({"font_color": "#000000", "num_format": "0.0%;[Red](0.0%);-"}),
        "integer": workbook.add_format({"font_color": "#000000", "num_format": "#,##0;[Red](#,##0);-"}),
        "date": workbook.add_format({"num_format": "yyyy-mm-dd"}),
        "total": workbook.add_format({"bold": True, "top": 1, "num_format": "#,##0.00;[Red](#,##0.00);-"}),
        "kpi_label": workbook.add_format({"bold": True, "font_color": "#44546A", "align": "left"}),
        "kpi": workbook.add_format({"bold": True, "font_size": 15, "font_color": "#17365D", "num_format": "#,##0.00;[Red](#,##0.00);-"}),
        "note": workbook.add_format({"font_color": "#666666", "italic": True, "text_wrap": True, "valign": "top"}),
        "ok": workbook.add_format({"bold": True, "font_color": "#006100", "bg_color": "#C6EFCE", "align": "center"}),
        "fail": workbook.add_format({"bold": True, "font_color": "#9C0006", "bg_color": "#FFC7CE", "align": "center"}),
    }


def _setup(sheet, widths: dict[str, float] | None = None) -> None:
    sheet.hide_gridlines(2)
    sheet.freeze_panes(3, 1)
    sheet.set_default_row(18)
    for column, width in (widths or {}).items():
        sheet.set_column(column, width)


def _title(sheet, text: str, formats: dict, last_col: str = "H") -> None:
    sheet.merge_range(f"A1:{last_col}1", text, formats["title"])
    sheet.set_row(0, 30)


def _write_frame(sheet, frame: pd.DataFrame, start_row: int, formats: dict, table_name: str) -> None:
    rows, columns = frame.shape
    if not columns:
        return
    display_names = [str(name) if " " in str(name) else str(name).replace("_", " ").title() for name in frame.columns]
    sheet.set_row(start_row, 34)
    for col, name in enumerate(frame.columns):
        sheet.write(start_row, col, display_names[col], formats["header"])
    for row_index, row in enumerate(frame.itertuples(index=False, name=None), start=start_row + 1):
        for col_index, value in enumerate(row):
            if pd.isna(value):
                sheet.write_blank(row_index, col_index, None)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                sheet.write_number(row_index, col_index, float(value))
            else:
                sheet.write(row_index, col_index, value)
    if rows:
        sheet.add_table(start_row, 0, start_row + rows, columns - 1, {
            "name": table_name,
            "style": "Table Style Medium 2",
            "columns": [{"header": display_names[index]} for index, name in enumerate(frame.columns)],
        })


def build_report() -> Path:
    run, summary = _latest_run()
    sa_run = ROOT / "outputs" / summary["sa_run_id"]
    sa_summary = json.loads((sa_run / "16_capital_summary.json").read_text(encoding="utf-8"))
    desk = _read(run, "25_desk_capital_summary")
    scaled_es = _read(run, "11_scaled_es_and_imcc")
    rfet = _read(run, "03_rfet_results")
    backtesting = _read(run, "22_backtesting_summary")
    sbm_classes = pd.read_csv(sa_run / "09_sbm_class_results.csv")
    sources = yaml.safe_load((ROOT / "config/regulatory/basel_2026_08_25/source_manifest.yaml").read_text(encoding="utf-8"))["sources"]

    output = run / "FRTB_Market_Risk_Report.xlsx"
    workbook = xlsxwriter.Workbook(output)
    workbook.set_properties({
        "title": "FRTB Market Risk Engine Report",
        "subject": "Basel FRTB Standardised Approach and Internal Models Approach",
        "author": "FRTB Market Risk Engine",
        "company": "",
        "comments": "Synthetic portfolio inputs with Basel regulatory parameters stored separately.",
    })
    formats = _formats(workbook)

    cover = workbook.add_worksheet("Overview")
    _setup(cover, {"A:A": 34, "B:B": 18, "C:C": 3, "D:K": 14})
    _title(cover, "FRTB Market Risk Engine", formats, "K")
    cover.write("A3", "Valuation date", formats["kpi_label"])
    cover.write("B3", summary["valuation_date"])
    cover.write("A4", "Reporting currency and unit", formats["kpi_label"])
    cover.write("B4", "INR crore")
    kpis = [
        ("Final market-risk capital", "='IMA Summary'!B18", summary["final_frtb_market_risk_capital_inr"] / INR_CRORE),
        ("Market RWA", "='IMA Summary'!B19", summary["market_rwa_inr"] / INR_CRORE),
        ("Full-book SA benchmark", "='SA Summary'!B8", sa_summary["frtb_sa_capital_inr"] / INR_CRORE),
        ("Eligible-desk SA share", "='IMA Summary'!B12", summary["eligible_sa_share"]),
    ]
    for row, (label, formula, cached) in enumerate(kpis, start=5):
        cover.write(row - 1, 0, label, formats["kpi_label"])
        cover.write_formula(row - 1, 1, formula, formats["percent"] if "share" in label.lower() else formats["kpi"], cached)
    cover.merge_range("A11:B13", "The report uses one synthetic INR trading book for SA and IMA. Synthetic market, RFET and portfolio histories remain distinct from versioned Basel parameters.", formats["note"])

    sa = workbook.add_worksheet("SA Summary")
    _setup(sa, {"A:A": 34, "B:B": 18, "D:J": 14})
    _title(sa, "Standardised Approach capital", formats, "J")
    sa.write_row("A3", ["Component", "INR crore"], formats["header"])
    sa_components = [
        ("Sensitivities-based Method", sa_summary["sbm_capital_inr"] / INR_CRORE),
        ("Default Risk Charge", sa_summary["drc_capital_inr"] / INR_CRORE),
        ("Residual Risk Add-on", sa_summary["rrao_capital_inr"] / INR_CRORE),
    ]
    for row, (label, value) in enumerate(sa_components, start=4):
        sa.write(row - 1, 0, label)
        sa.write_number(row - 1, 1, value, formats["linked"])
    total = sum(value for _, value in sa_components)
    sa.write("A8", "FRTB SA capital", formats["total"])
    sa.write_formula("B8", "=SUM(B4:B6)", formats["total"], total)
    sa.write("A9", "RWA multiplier")
    sa.write_number("B9", 12.5, formats["linked"])
    sa.write("A11", "Market RWA", formats["total"])
    sa.write_formula("B11", "=B8*B9", formats["total"], total * 12.5)
    chart = workbook.add_chart({"type": "column"})
    chart.add_series({"name": "SA capital", "categories": "='SA Summary'!$A$4:$A$6", "values": "='SA Summary'!$B$4:$B$6", "fill": {"color": "#4472C4"}})
    chart.set_title({"name": "SA capital by component (INR crore)"})
    chart.set_y_axis({"num_format": "#,##0.0"})
    chart.set_legend({"none": True})
    chart.set_size({"width": 650, "height": 330})
    sa.insert_chart("D3", chart)

    ima = workbook.add_worksheet("IMA Summary")
    _setup(ima, {"A:A": 42, "B:B": 18, "D:J": 14})
    _title(ima, "Internal Models Approach and SA fallback", formats, "J")
    ima.write_row("A3", ["Capital input or calculation", "INR crore / ratio"], formats["header"])
    inputs = [
        ("Current IMCC", summary["imcc_current_inr"] / INR_CRORE),
        ("60-day average IMCC", summary["imcc_average_60_day_inr"] / INR_CRORE),
        ("Backtesting multiplier", summary["backtesting_multiplier"]),
        ("Current SES", summary["ses_current_inr"] / INR_CRORE),
        ("60-day average SES", summary["ses_average_60_day_inr"] / INR_CRORE),
        ("IMA DRC capital", summary["ima_drc_capital_inr"] / INR_CRORE),
        ("PLA amber surcharge", summary["pla_amber_surcharge_inr"] / INR_CRORE),
        ("SA fallback capital", summary["sa_fallback_capital_inr"] / INR_CRORE),
        ("Eligible-desk SA share", summary["eligible_sa_share"]),
    ]
    for row, (label, value) in enumerate(inputs, start=4):
        ima.write(row - 1, 0, label)
        ima.write_number(row - 1, 1, value, formats["percent"] if "share" in label.lower() else formats["linked"])
    current_non_drc = (summary["imcc_current_inr"] + summary["ses_current_inr"]) / INR_CRORE
    average_non_drc = (summary["backtesting_multiplier"] * summary["imcc_average_60_day_inr"] + summary["ses_average_60_day_inr"]) / INR_CRORE
    eligible = summary["ima_eligible_capital_before_surcharge_inr"] / INR_CRORE
    final = summary["final_frtb_market_risk_capital_inr"] / INR_CRORE
    ima.write("A15", "Current non-DRC capital", formats["label"])
    ima.write_formula("B15", "=B4+B7", formats["formula"], current_non_drc)
    ima.write("A16", "Multiplier-adjusted average non-DRC", formats["label"])
    ima.write_formula("B16", "=B5*B6+B8", formats["formula"], average_non_drc)
    ima.write("A17", "IMA eligible capital before surcharge", formats["label"])
    ima.write_formula("B17", "=MAX(B15,B16)+B9", formats["formula"], eligible)
    ima.write("A18", "Final market-risk capital", formats["total"])
    ima.write_formula("B18", "=B17+B10+B11", formats["total"], final)
    ima.write("A19", "Market RWA", formats["total"])
    ima.write_formula("B19", "=B18*12.5", formats["total"], final * 12.5)
    ima.write("A21", "Amber surcharge rule", formats["kpi_label"])
    ima.merge_range("A22:B23", "k = 0.5 × standalone SA of amber desks ÷ standalone SA of green and amber desks; surcharge = k × max(SA eligible − IMA eligible, 0).", formats["note"])
    ima_chart = workbook.add_chart({"type": "column"})
    ima_chart.add_series({"name": "Capital", "categories": "='IMA Summary'!$A$9:$A$11", "values": "='IMA Summary'!$B$9:$B$11", "fill": {"color": "#70AD47"}})
    ima_chart.set_title({"name": "IMA, surcharge and fallback inputs (INR crore)"})
    ima_chart.set_y_axis({"num_format": "#,##0.0"})
    ima_chart.set_legend({"none": True})
    ima_chart.set_size({"width": 650, "height": 330})
    ima.insert_chart("D3", ima_chart)

    desk_sheet = workbook.add_worksheet("Desk Treatment")
    _setup(desk_sheet, {"A:A": 18, "B:B": 18, "C:G": 20, "H:H": 72})
    _title(desk_sheet, "Desk eligibility and capital treatment", formats, "H")
    desk_columns = [
        "desk", "final_treatment", "sa_capital_inr", "ima_component_inr",
        "amber_surcharge_inr", "sa_fallback_component_inr", "final_capital_treatment_inr",
        "eligibility_reason",
    ]
    desk_view = desk[desk_columns].copy()
    for column in [name for name in desk_columns if name.endswith("_inr")]:
        desk_view[column] = pd.to_numeric(desk_view[column]) / INR_CRORE
    desk_view.columns = [
        "Desk", "Final treatment", "Standalone SA (INR crore)", "Allocated IMA (INR crore)",
        "Amber surcharge (INR crore)", "SA fallback (INR crore)",
        "Final allocated capital (INR crore)", "Eligibility reason",
    ]
    _write_frame(desk_sheet, desk_view, 2, formats, "DeskTreatmentTable")
    desk_sheet.set_column("C:G", 20, formats["crore"])
    desk_sheet.write(len(desk_view) + 4, 5, "Desk allocation total", formats["total"])
    desk_sheet.write_formula(len(desk_view) + 4, 6, f"=SUM(G4:G{3 + len(desk_view)})", formats["total"], final)

    es_sheet = workbook.add_worksheet("ES and IMCC")
    _setup(es_sheet, {"A:A": 24, "B:H": 20})
    _title(es_sheet, "Expected Shortfall scaling and IMCC", formats, "I")
    es_view = scaled_es.copy()
    money_columns = [column for column in es_view if column.endswith("_inr")]
    for column in money_columns:
        es_view[column] = pd.to_numeric(es_view[column]) / INR_CRORE
    es_view["coverage_pass"] = es_view["coverage_pass"].map({True: "PASS", False: "REVIEW", "True": "PASS", "False": "REVIEW"}).fillna(es_view["coverage_pass"])
    es_view = es_view.rename(columns={
        "scope": "Scope", "full_current_es_inr": "Full current ES (INR crore)",
        "reduced_current_es_inr": "Reduced current ES (INR crore)",
        "reduced_stress_es_inr": "Reduced stress ES (INR crore)",
        "reduced_set_coverage": "Reduced-set coverage", "stress_scaling_ratio": "Stress scaling ratio",
        "scaled_es_capital_inr": "Scaled ES capital (INR crore)",
        "coverage_requirement": "Coverage requirement", "coverage_pass": "Coverage status",
    })
    _write_frame(es_sheet, es_view, 2, formats, "ScaledESTable")
    for index, column in enumerate(es_view.columns):
        if "(INR crore)" in column:
            es_sheet.set_column(index, index, 20, formats["crore"])
        elif column in {"Reduced-set coverage", "Coverage requirement"}:
            es_sheet.set_column(index, index, 18, formats["percent"])
        elif "ratio" in column.lower():
            es_sheet.set_column(index, index, 18, formats["formula"])

    rfet_sheet = workbook.add_worksheet("RFET")
    _setup(rfet_sheet, {"A:A": 38, "B:B": 20, "C:C": 22, "D:D": 28, "E:E": 30, "F:F": 20, "G:G": 74})
    _title(rfet_sheet, "Risk Factor Eligibility Test", formats, "G")
    rfet_view = rfet[[
        "risk_factor_id", "broad_risk_class", "qualifying_observation_count",
        "minimum_observations_in_any_90_days", "rfet_route", "modellability_status", "rfet_reason",
    ]].rename(columns={
        "risk_factor_id": "Risk factor ID", "broad_risk_class": "Broad risk class",
        "qualifying_observation_count": "Observation count",
        "minimum_observations_in_any_90_days": "Minimum count in any 90 days",
        "rfet_route": "RFET route", "modellability_status": "Modellability status",
        "rfet_reason": "RFET result explanation",
    })
    _write_frame(rfet_sheet, rfet_view, 2, formats, "RFETTable")

    bt_sheet = workbook.add_worksheet("Backtesting")
    _setup(bt_sheet, {"A:A": 18, "B:I": 18, "J:J": 54})
    _title(bt_sheet, "Desk backtesting results", formats, "J")
    backtesting_view = backtesting.rename(columns={
        "desk": "Desk", "observations": "Observations",
        "hpl_exceptions_97_5": "HPL exceptions (97.5%)", "hpl_exceptions_99": "HPL exceptions (99%)",
        "apl_exceptions_97_5": "APL exceptions (97.5%)", "apl_exceptions_99": "APL exceptions (99%)",
        "exceptions_used_97_5": "Exceptions used (97.5%)", "exceptions_used_99": "Exceptions used (99%)",
        "backtesting_result": "Backtesting result", "backtesting_reason": "Backtesting explanation",
    })
    _write_frame(bt_sheet, backtesting_view, 2, formats, "BacktestingTable")

    sbm_sheet = workbook.add_worksheet("SBM Classes")
    _setup(sbm_sheet, {"A:A": 16, "B:B": 40, "C:C": 20, "D:D": 20})
    _title(sbm_sheet, "Seven SBM risk classes by measure and scenario", formats, "D")
    if "capital" in sbm_classes:
        sbm_classes["capital"] = pd.to_numeric(sbm_classes["capital"]) / INR_CRORE
    sbm_classes = sbm_classes.rename(columns={
        "scenario": "Scenario", "risk_class": "Risk class",
        "capital": "Capital (INR crore)", "risk_measure": "Risk measure",
    })
    _write_frame(sbm_sheet, sbm_classes, 2, formats, "SBMClassTable")
    if "Capital (INR crore)" in sbm_classes:
        capital_col = list(sbm_classes.columns).index("Capital (INR crore)")
        sbm_sheet.set_column(capital_col, capital_col, 20, formats["crore"])

    checks = workbook.add_worksheet("Checks")
    _setup(checks, {"A:A": 34, "B:D": 18, "E:E": 14, "F:F": 48})
    _title(checks, "Formula and capital checks", formats, "F")
    checks.write_row("A3", ["Check", "Actual", "Expected", "Difference", "Status", "Notes"], formats["header"])
    check_rows = [
        ("SA capital equals three components", "='SA Summary'!B8", sa_summary["frtb_sa_capital_inr"] / INR_CRORE, "SBM + DRC + RRAO"),
        ("SA RWA equals capital times 12.5", "='SA Summary'!B11", sa_summary["market_rwa_inr"] / INR_CRORE, "Capital conversion"),
        ("Final capital equals IMA, surcharge and fallback", "='IMA Summary'!B18", final, "Combined capital"),
        ("Market RWA equals final capital times 12.5", "='IMA Summary'!B19", summary["market_rwa_inr"] / INR_CRORE, "Capital conversion"),
        ("Desk allocations equal final capital", f"='Desk Treatment'!G{len(desk_view) + 5}", final, "Allocation presentation"),
    ]
    for row, (label, actual_formula, expected, note) in enumerate(check_rows, start=4):
        checks.write(row - 1, 0, label)
        checks.write_formula(row - 1, 1, actual_formula, formats["formula"], expected)
        checks.write_number(row - 1, 2, expected, formats["linked"])
        checks.write_formula(row - 1, 3, f"=B{row}-C{row}", formats["formula"], 0.0)
        checks.write_formula(row - 1, 4, f'=IF(ABS(D{row})<0.01,"OK","REVIEW")', formats["ok"], "OK")
        checks.write(row - 1, 5, note)
    checks.conditional_format(3, 4, 3 + len(check_rows) - 1, 4, {"type": "text", "criteria": "containing", "value": "REVIEW", "format": formats["fail"]})

    source_sheet = workbook.add_worksheet("Sources")
    _setup(source_sheet, {"A:A": 30, "B:B": 55, "C:C": 70, "D:D": 18, "E:E": 48})
    _title(source_sheet, "Regulatory sources and data boundary", formats, "E")
    source_sheet.write_row("A3", ["Source ID", "Title", "URL", "Accessed on", "Purpose"], formats["header"])
    for row, source in enumerate(sources, start=4):
        source_sheet.write(row - 1, 0, source["source_id"])
        source_sheet.write(row - 1, 1, source["title"])
        source_sheet.write_url(row - 1, 2, source["url"], string=source["url"])
        source_sheet.write(row - 1, 3, str(source["accessed_on"]))
        source_sheet.write(row - 1, 4, source["purpose"])
    note_row = 4 + len(sources) + 2
    source_sheet.merge_range(note_row, 0, note_row + 2, 4, "Synthetic inputs: 48 trades, market snapshot, factor history, RFET evidence and dated position snapshots. Regulatory inputs: versioned Basel risk weights, correlations, liquidity horizons, eligibility thresholds and capital aggregation rules.", formats["note"])

    workbook.close()
    return output


if __name__ == "__main__":
    print(build_report())
