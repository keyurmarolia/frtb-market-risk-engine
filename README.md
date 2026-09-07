# FRTB Market Risk Engine

## Version and scope

This is an educational project snapshot. Saved results describe the current local version; they have not been independently revalidated for this release. Methodology and validation updates will be documented in future revisions.

The model is under review. Saved notebook results may predate changes to the calculation code and should be treated as illustrative until a reconciled rerun is completed.

This Python project calculates Basel Fundamental Review of the Trading Book market-risk capital under both the Standardised Approach and the Internal Models Approach using one shared synthetic trading book.

## Complete calculation boundary

```text
Shared trading book and INR market data
                 |
       Pricing and risk factors
          /                \
Standardised Approach   Internal Models Approach
SBM + SA DRC + RRAO     RFET -> MRF / NMRF
                       MRF -> ES -> IMCC
                       NMRF -> SES
                       Default risk -> IMA DRC
                       PLA + backtesting -> desk eligibility
          \                /
       IMA eligible desks + SA fallback desks
                 |
      Final FRTB market-risk capital
                 |
              x 12.5
                 |
             Market RWA
```

INR is the reporting currency. Foreign positions retain their native currency and generate the relevant FX exposure against INR.

## Data and regulatory parameters

- The 48 trades, valuation market snapshot, ten-year factor history, RFET observations and 501 position dates are explicitly labelled synthetic. The position dates produce 500 prior-day-to-next-day P&L outcomes.
- Synthetic history is generated from correlated economic drivers, volatility clustering, named stress regimes and fixed random seeds.
- RFET records represent synthetic transaction and committed-quote events; they are not public closing prices.
- Basel parameters are stored separately under `config/regulatory/basel_2026_08_25/` with source lineage to MAR20–MAR23 and MAR30–MAR33.
- Every completed calculation retains factor, desk, trade, date and scenario detail.

## Chronological notebooks

The 47 pre-executed notebooks form one continuous calculation.

- `00`–`05`: trading book, market data, pricing and factor mapping
- `06`–`17`: delta, vega and curvature by risk class and derivatives portfolio
- `18`–`22`: exact-factor netting, weights, correlations and seven-class SBM
- `23`–`29`: SA DRC, RRAO, SA capital and trade walkthrough
- `30`–`38`: IMA map, RFET, liquidity horizons, historical P&L, ES, IMCC and NMRF SES
- `39`–`44`: IMA DRC, daily portfolios, HPL/RTPL, PLA, VaR backtesting, eligibility and IMA aggregation
- `45`–`46`: combined SA/IMA capital, Market RWA, reporting and lineage

Each notebook states the calculation, purpose, inputs, formula, numerical example and interpretation. Monetary displays use INR or INR crore without scientific notation.

## Reproducible execution

```bash
python3 scripts/bootstrap_environment.py
.frtb_sa_env/bin/python -m frtb_engine validate-foundation
.frtb_sa_env/bin/python -m frtb_engine run-ima
.frtb_sa_env/bin/python scripts/build_notebooks.py
.frtb_sa_env/bin/python scripts/build_ima_notebooks.py
.frtb_sa_env/bin/python scripts/validate_notebooks.py
.frtb_sa_env/bin/python scripts/build_report.py
.frtb_sa_env/bin/python -m pytest -q
```

`Run FRTB Market Risk Engine.command` runs the complete integrated calculation and opens the retained outputs.

## Project structure

- `data/synthetic/` — shared trades, market snapshot and generated IMA history
- `config/regulatory/` — Basel parameters and source lineage
- `src/frtb_engine/pricing.py` — common transparent valuation functions
- `src/frtb_engine/sensitivities.py` — common trade-to-factor mapping and repricing sensitivities
- `src/frtb_engine/sbm.py`, `drc.py`, `rrao.py` — Standardised Approach calculations
- `src/frtb_engine/ima.py` — RFET, ES, IMCC, SES, IMA DRC, PLA and backtesting calculations
- `src/frtb_engine/ima_pipeline.py` — desk eligibility, SA fallback and combined capital
- `docs/` — calculation methodology, scope, architecture, data definitions and notebook sequence
- `notebooks/` — 47 pre-executed chronological notebooks
- `tests/` — formula, regulatory-control, lineage and end-to-end tests
- `outputs/` — generated run artifacts and a formula-driven reporting workbook

## Interpretation boundary

The engine is a Basel-aligned educational implementation using synthetic data and transparent pricing approximations. It is not a bank-approved internal model, an RBI filing or evidence of supervisory model approval.

## Related projects

[Credit scorecard](https://github.com/keyurmarolia/credit-scorecard-pd-model) · [IFRS 9 ECL](https://github.com/keyurmarolia/ifrs9-mortgage-ecl) · [Basel capital](https://github.com/keyurmarolia/basel-credit-capital-engine) · [FRTB](https://github.com/keyurmarolia/frtb-market-risk-engine) · [Momentum](https://github.com/keyurmarolia/momentum-strategy-research) · [IndiGo research](https://github.com/keyurmarolia/indigo-equity-research)
