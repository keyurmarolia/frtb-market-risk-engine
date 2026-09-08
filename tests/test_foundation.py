import sqlite3
from pathlib import Path

from frtb_engine.config import load_project_config, load_regulatory_manifest
from frtb_engine.database import EXPECTED_TABLES, initialise_database, schema_summary
from frtb_engine.validation import SEVEN_SBM_RISK_CLASSES, foundation_errors


def test_foundation_configuration_passes() -> None:
    assert foundation_errors() == []


def test_reporting_currency_is_inr() -> None:
    config = load_project_config()
    assert config["project"]["reporting_currency"] == "INR"
    assert config["project"]["base_currency"] == "INR"


def test_one_portfolio_is_shared_by_sa_and_ima() -> None:
    config = load_project_config()
    assert set(config["portfolio"]["shared_across_methods"]) == {"SA", "IMA"}
    assert set(config["engines"]["methods"]) == {"SA", "IMA"}
    assert config["engines"]["shares_pricing_and_risk_factors"] is True


def test_all_seven_sbm_risk_classes_are_configured() -> None:
    config = load_project_config()
    assert set(config["engines"]["sbm_risk_classes"]) == SEVEN_SBM_RISK_CLASSES


def test_manifest_covers_sa_and_ima_chapters() -> None:
    manifest = load_regulatory_manifest()
    assert set(manifest["required_components"]) == {
        "MAR20", "MAR21", "MAR22", "MAR23", "MAR30", "MAR31", "MAR32", "MAR33",
    }
    assert manifest["parameter_set"]["basis"] == "Basel global minimum standard"


def test_shared_database_schema_and_seed_records(tmp_path: Path) -> None:
    database = initialise_database(tmp_path / "frtb_test.sqlite3")
    summary = schema_summary(database)
    assert summary["schema_version"] == "3"
    assert set(summary["tables"]) == EXPECTED_TABLES

    with sqlite3.connect(database) as connection:
        portfolio = connection.execute(
            "SELECT portfolio_id, reporting_currency, data_classification FROM portfolios"
        ).fetchone()
        parameter_sets = connection.execute(
            "SELECT parameter_set_id, basis FROM regulatory_parameter_sets ORDER BY parameter_set_id"
        ).fetchall()

    assert portfolio == ("INDIA_SYNTHETIC_TRADING_BOOK", "INR", "synthetic")
    assert parameter_sets == [
        ("BASEL_FRTB_IMA_2026_08_25", "Basel global minimum standard"),
        ("BASEL_FRTB_SA_2026_08_25", "Basel global minimum standard"),
    ]
