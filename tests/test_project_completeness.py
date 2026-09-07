import json
import re
import sqlite3
from pathlib import Path

import nbformat
import pandas as pd

from frtb_engine.config import load_regulatory_manifest, load_sbm_parameters
from frtb_engine.database import database_path


ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_book_activates_all_desks_and_seven_sbm_classes() -> None:
    trades = pd.read_csv(ROOT / "data/synthetic/trades.csv", keep_default_na=False)
    assert len(trades) == 48
    assert set(trades["desk"]) == {"Rates", "Credit", "Equity", "FX", "Commodity", "Residual Risk"}
    classes = set(trades.loc[trades["csr_class"] != "NONE", "csr_class"])
    assert classes == {"CSR_NON_SECURITISATION", "CSR_SECURITISATION_NON_CTP", "CSR_SECURITISATION_CTP"}


def test_regulatory_parameter_files_are_loaded_and_complete() -> None:
    manifest = load_regulatory_manifest()
    params = load_sbm_parameters()
    assert manifest["parameter_set"]["status"] == "educational_parameter_set_loaded_and_validated"
    assert len(params["delta_risk_weights"]["GIRR"]["tenors"]) == 10
    assert len(params["delta_risk_weights"]["CSR_NON_SECURITISATION"]["buckets"]) == 18
    assert len(params["delta_risk_weights"]["CSR_SECURITISATION_CTP"]["buckets"]) == 16
    assert len(params["delta_risk_weights"]["EQUITY"]["spot_buckets"]) == 13
    assert len(params["delta_risk_weights"]["COMMODITY"]["buckets"]) == 11


def test_all_forty_seven_notebooks_are_executed_without_error_outputs() -> None:
    notebooks = sorted((ROOT / "notebooks").glob("*.ipynb"))
    assert len(notebooks) == 47
    for path in notebooks:
        notebook = nbformat.read(path, as_version=4)
        code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
        assert code_cells, path.name
        assert all(cell.execution_count is not None for cell in code_cells), path.name
        assert not any(output.output_type == "error" for cell in code_cells for output in cell.outputs), path.name


def test_notebooks_are_visual_and_do_not_show_scientific_notation() -> None:
    scientific = re.compile(r"(?<![A-Za-z0-9_])[+-]?\d+(?:\.\d+)?e[+-]?\d+", re.IGNORECASE)
    for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
        notebook = nbformat.read(path, as_version=4)
        image_count = 0
        visible_text = []
        for cell in notebook.cells:
            for output in cell.get("outputs", []):
                data = output.get("data", {})
                image_count += int(any(key.startswith("image/") for key in data))
                visible_text.extend(str(data.get(key, "")) for key in ("text/plain", "text/html"))
                visible_text.append(str(output.get("text", "")))
        assert image_count >= 2, path.name
        rendered = " ".join(visible_text)
        assert not scientific.search(rendered), path.name
        assert not re.search(r"\bNaN\b", rendered), path.name


def test_notebooks_do_not_contain_generic_reconciliation_sections() -> None:
    banned = ("## Reconciliation", "Reconciled ")
    for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
        notebook = nbformat.read(path, as_version=4)
        source = "\n".join(cell.source for cell in notebook.cells)
        assert not any(phrase in source for phrase in banned), path.name


def test_ima_visuals_have_specific_explanations_and_no_generic_handoff() -> None:
    banned = (
        "The displayed result is the retained production calculation",
        "The next notebook reads this output",
    )
    for path in sorted((ROOT / "notebooks").glob("*.ipynb"))[30:47]:
        notebook = nbformat.read(path, as_version=4)
        source = "\n".join(cell.source for cell in notebook.cells)
        assert not any(phrase in source for phrase in banned), path.name
        for index, cell in enumerate(notebook.cells):
            is_visual = cell.cell_type == "code" and any(
                marker in cell.source for marker in ("plt.show()", "heatmap(", "draw_flow(")
            )
            if is_visual:
                assert index + 1 < len(notebook.cells), path.name
                explanation = notebook.cells[index + 1]
                assert explanation.cell_type == "markdown", path.name
                assert len(explanation.source) >= 180, path.name


def test_liquidity_horizon_notebook_distinguishes_assignment_from_nesting() -> None:
    notebook = nbformat.read(ROOT / "notebooks/33_liquidity_horizons.ipynb", as_version=4)
    source = "\n".join(cell.source for cell in notebook.cells)
    assert "Displayed sample: first 30 of" in source
    assert "The sample does not contain every horizon" in source
    assert "Number of risk factors assigned to each liquidity horizon" in source
    assert "It is not the nested Expected Shortfall calculation" in source
    assert "nesting of these horizon groups is calculated in notebook 35" in source


def test_girr_and_weighting_notebooks_explain_special_factors_and_schedules() -> None:
    girr = nbformat.read(ROOT / "notebooks/06_girr_delta.ipynb", as_version=4)
    girr_source = "\n".join(cell.source for cell in girr.cells)
    assert "Not applicable — flat cross-currency basis factor" in girr_source
    assert "Portfolio GIRR value change for a +1 basis-point shock" in girr_source
    weighting = nbformat.read(ROOT / "notebooks/18_regulatory_weights_and_weighted_sensitivities.ipynb", as_version=4)
    weighting_source = "\n".join(cell.source for cell in weighting.cells)
    assert "Complete delta risk-weight schedule" in weighting_source
    assert "Complete vega risk-weight schedule" in weighting_source


def test_shared_database_integrity_and_completed_sa_run() -> None:
    with sqlite3.connect(database_path()) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        methods = {row[0] for row in connection.execute("SELECT DISTINCT engine_method FROM trade_engine_scope")}
        completed = connection.execute("SELECT COUNT(*) FROM engine_runs WHERE engine_method='SA' AND status='completed'").fetchone()[0]
    assert methods == {"SA", "IMA"}
    assert completed >= 1
