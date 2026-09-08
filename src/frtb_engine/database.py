"""Shared SQLite schema for the integrated FRTB SA and IMA calculations."""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List

from frtb_engine.config import PROJECT_ROOT, load_project_config


SCHEMA_VERSION = "3"

EXPECTED_TABLES = {
    "schema_metadata",
    "portfolios",
    "trades",
    "trade_attributes",
    "trade_engine_scope",
    "market_data_sets",
    "market_data_values",
    "regulatory_parameter_sets",
    "engine_runs",
    "run_artifacts",
}


DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolios (
    portfolio_id TEXT PRIMARY KEY,
    portfolio_name TEXT NOT NULL,
    jurisdiction_context TEXT NOT NULL,
    reporting_currency TEXT NOT NULL,
    base_currency TEXT NOT NULL,
    data_classification TEXT NOT NULL CHECK (data_classification IN ('synthetic', 'external', 'mixed'))
);

CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL REFERENCES portfolios(portfolio_id),
    desk TEXT NOT NULL,
    sub_portfolio TEXT NOT NULL,
    instrument_type TEXT NOT NULL,
    product_form TEXT NOT NULL CHECK (product_form IN ('cash', 'derivative')),
    trade_currency TEXT NOT NULL,
    reporting_currency TEXT NOT NULL,
    quantity REAL,
    notional REAL,
    market_value REAL,
    long_short TEXT NOT NULL CHECK (long_short IN ('long', 'short')),
    underlying TEXT,
    issuer TEXT,
    maturity_years REAL,
    option_expiry_years REAL,
    is_synthetic INTEGER NOT NULL CHECK (is_synthetic IN (0, 1)),
    source_label TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trade_engine_scope (
    trade_id TEXT NOT NULL REFERENCES trades(trade_id),
    engine_method TEXT NOT NULL CHECK (engine_method IN ('SA', 'IMA')),
    in_scope INTEGER NOT NULL CHECK (in_scope IN (0, 1)),
    scope_reason TEXT NOT NULL,
    PRIMARY KEY (trade_id, engine_method)
);

CREATE TABLE IF NOT EXISTS trade_attributes (
    trade_id TEXT PRIMARY KEY REFERENCES trades(trade_id),
    attributes_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_data_sets (
    market_data_set_id TEXT PRIMARY KEY,
    valuation_date TEXT NOT NULL,
    reporting_currency TEXT NOT NULL,
    data_classification TEXT NOT NULL CHECK (data_classification IN ('synthetic', 'external', 'mixed')),
    source_manifest_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_data_values (
    market_data_set_id TEXT NOT NULL REFERENCES market_data_sets(market_data_set_id),
    risk_factor_group TEXT NOT NULL,
    risk_factor_key TEXT NOT NULL,
    tenor TEXT NOT NULL DEFAULT '',
    value REAL NOT NULL,
    is_synthetic INTEGER NOT NULL CHECK (is_synthetic IN (0, 1)),
    PRIMARY KEY (market_data_set_id, risk_factor_group, risk_factor_key, tenor)
);

CREATE TABLE IF NOT EXISTS regulatory_parameter_sets (
    parameter_set_id TEXT PRIMARY KEY,
    framework TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    basis TEXT NOT NULL,
    source_manifest_path TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS engine_runs (
    run_id TEXT PRIMARY KEY,
    engine_method TEXT NOT NULL CHECK (engine_method IN ('SA', 'IMA')),
    portfolio_id TEXT NOT NULL REFERENCES portfolios(portfolio_id),
    market_data_set_id TEXT REFERENCES market_data_sets(market_data_set_id),
    parameter_set_id TEXT REFERENCES regulatory_parameter_sets(parameter_set_id),
    reporting_currency TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed'))
);

CREATE TABLE IF NOT EXISTS run_artifacts (
    run_id TEXT NOT NULL REFERENCES engine_runs(run_id),
    calculation_stage TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    sha256 TEXT,
    row_count INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, calculation_stage, artifact_path)
);
"""


def database_path() -> Path:
    config = load_project_config()
    return PROJECT_ROOT / config["portfolio"]["database_path"]


def initialise_database(path: Path | None = None) -> Path:
    """Create the common schema and register the base portfolio and Basel snapshot."""
    config = load_project_config()
    target = path or database_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(target) as connection:
        connection.executescript(DDL)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(trades)")}
        for old, new in (("maturity_date", "maturity_years"), ("option_expiry", "option_expiry_years")):
            if old in columns:
                connection.execute(f"ALTER TABLE trades ADD COLUMN {new} REAL")
                connection.execute(f"UPDATE trades SET {new} = CAST({old} AS REAL)")
                connection.execute(f"ALTER TABLE trades DROP COLUMN {old}")
        connection.execute(
            "INSERT OR REPLACE INTO schema_metadata(key, value) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO portfolios(
                portfolio_id, portfolio_name, jurisdiction_context,
                reporting_currency, base_currency, data_classification
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                config["portfolio"]["portfolio_id"],
                config["portfolio"]["name"],
                config["project"]["jurisdiction_context"],
                config["project"]["reporting_currency"],
                config["project"]["base_currency"],
                config["project"]["data_classification"],
            ),
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO regulatory_parameter_sets(
                parameter_set_id, framework, snapshot_date, effective_date,
                basis, source_manifest_path, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "BASEL_FRTB_SA_2026_08_25",
                "Basel Framework",
                "2026-08-25",
                "2023-01-01",
                "Basel global minimum standard",
                config["provenance"]["regulatory_manifest"],
                "educational_parameter_set_loaded_and_validated",
            ),
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO regulatory_parameter_sets(
                parameter_set_id, framework, snapshot_date, effective_date,
                basis, source_manifest_path, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "BASEL_FRTB_IMA_2026_08_25",
                "Basel Framework",
                "2026-08-25",
                "2023-01-01",
                "Basel global minimum standard",
                config["provenance"]["regulatory_manifest"],
                "educational_parameter_set_loaded_and_validated",
            ),
        )
        connection.commit()
    return target


def schema_summary(path: Path | None = None) -> Dict[str, List[str] | str]:
    target = path or database_path()
    with sqlite3.connect(target) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
        version_row = connection.execute(
            "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
        ).fetchone()
    return {
        "schema_version": version_row[0] if version_row else "missing",
        "tables": [row[0] for row in rows],
    }


def load_synthetic_book(path: Path | None = None) -> Dict[str, int]:
    """Load the CSV trading book and YAML market data into the shared database."""
    import pandas as pd

    from frtb_engine.config import load_market_data

    config = load_project_config()
    target = initialise_database(path)
    trades = pd.read_csv(PROJECT_ROOT / "data/synthetic/trades.csv", keep_default_na=False)
    market = load_market_data()
    portfolio_id = config["portfolio"]["portfolio_id"]
    market_set_id = "SYNTHETIC_MARKET_2026_06_30"

    with sqlite3.connect(target) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("DELETE FROM trade_engine_scope")
        connection.execute("DELETE FROM trade_attributes")
        connection.execute("DELETE FROM trades")
        for record in trades.to_dict(orient="records"):
            connection.execute(
                """
                INSERT INTO trades(
                    trade_id, portfolio_id, desk, sub_portfolio, instrument_type,
                    product_form, trade_currency, reporting_currency, quantity,
                    notional, market_value, long_short, underlying, issuer,
                    maturity_years, option_expiry_years, is_synthetic, source_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["trade_id"], portfolio_id, record["desk"],
                    record["sub_portfolio"], record["instrument_type"],
                    record["product_form"], record["currency"], "INR",
                    float(record["quantity"]), float(record["notional"]), None,
                    record["long_short"], record["underlying"], record["issuer"],
                    float(record["maturity_years"]), float(record["option_expiry_years"]),
                    1, "data/synthetic/trades.csv",
                ),
            )
            connection.execute(
                "INSERT INTO trade_attributes(trade_id, attributes_json) VALUES (?, ?)",
                (record["trade_id"], json.dumps(record, sort_keys=True)),
            )
            connection.execute(
                "INSERT INTO trade_engine_scope VALUES (?, 'SA', 1, 'Synthetic SA coverage portfolio')",
                (record["trade_id"],),
            )
            connection.execute(
                "INSERT INTO trade_engine_scope VALUES (?, 'IMA', 1, 'Same trade and pricing foundation used for IMA desk assessment')",
                (record["trade_id"],),
            )

        connection.execute(
            """
            INSERT OR REPLACE INTO market_data_sets(
                market_data_set_id, valuation_date, reporting_currency,
                data_classification, source_manifest_path
            ) VALUES (?, ?, ?, 'synthetic', ?)
            """,
            (market_set_id, str(market["valuation_date"]), "INR", "data/synthetic/market_data.yaml"),
        )
        connection.execute("DELETE FROM market_data_values WHERE market_data_set_id = ?", (market_set_id,))
        market_rows = _flatten_market_data(market_set_id, market)
        connection.executemany(
            "INSERT INTO market_data_values VALUES (?, ?, ?, ?, ?, 1)", market_rows
        )
        connection.commit()

    return {"trades": len(trades), "market_data_values": len(market_rows)}


def _flatten_market_data(market_set_id: str, market: Dict) -> List[tuple]:
    rows: List[tuple] = []
    for group, values in market.items():
        if group in {"valuation_date", "reporting_currency", "data_classification"}:
            continue
        for key, value in values.items():
            if isinstance(value, dict):
                for tenor, number in value.items():
                    rows.append((market_set_id, group, str(key), str(tenor), float(number)))
            else:
                rows.append((market_set_id, group, str(key), "", float(value)))
    return rows
