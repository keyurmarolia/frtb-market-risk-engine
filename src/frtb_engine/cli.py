"""Command-line entry points for clear, reproducible project checks."""

import argparse

from frtb_engine.database import initialise_database, load_synthetic_book, schema_summary
from frtb_engine.validation import validate_foundation
from frtb_engine.pipeline import run_sa
from frtb_engine.ima_pipeline import run_ima


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FRTB market risk engine")
    parser.add_argument(
        "command",
        choices=["validate-foundation", "init-db", "load-synthetic-book", "run-sa", "run-ima"],
        help="Foundation action to perform",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    validate_foundation()

    if args.command == "validate-foundation":
        print("Foundation validation passed.")
        return

    if args.command == "load-synthetic-book":
        counts = load_synthetic_book()
        print(f"Synthetic book loaded: {counts['trades']} trades")
        print(f"Synthetic market data loaded: {counts['market_data_values']} values")
        return

    if args.command == "run-sa":
        summary = run_sa()
        print(f"FRTB SA run completed: {summary['run_id']}")
        print(f"Selected SBM scenario: {summary['sbm_selected_scenario']}")
        print(f"FRTB SA capital (INR): {summary['frtb_sa_capital_inr']:,.2f}")
        print(f"Market RWA (INR): {summary['market_rwa_inr']:,.2f}")
        return

    if args.command == "run-ima":
        summary = run_ima()
        print(f"FRTB IMA run completed: {summary['run_id']}")
        print(f"Eligible desks: {', '.join(summary['eligible_desks'])}")
        print(f"SA fallback desks: {', '.join(summary['fallback_desks'])}")
        print(f"Final FRTB market-risk capital (INR): {summary['final_frtb_market_risk_capital_inr']:,.2f}")
        print(f"Market RWA (INR): {summary['market_rwa_inr']:,.2f}")
        return

    path = initialise_database()
    summary = schema_summary(path)
    print(f"Shared database initialised: {path}")
    print(f"Schema version: {summary['schema_version']}")
    print(f"Tables: {', '.join(summary['tables'])}")
