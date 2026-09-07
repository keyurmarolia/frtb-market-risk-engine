# IMA synthetic data

The files in this directory are deterministic synthetic inputs for the Internal Models Approach calculation.

The factor history is generated from correlated rates, credit, equity, foreign-exchange and commodity drivers. It includes volatility clustering and named market-stress regimes. The final factor levels are anchored to the shared synthetic valuation snapshot.

RFET observation records represent synthetic transactions and committed quotes. They are not public closing prices and are not represented as observed regulatory evidence.

The 501 portfolio snapshots use the same 48 trades as the Standardised Approach and support 500 prior-day-to-next-day P&L outcomes. Position changes are generated from documented resizing and hedge-adjustment rules with fixed random seeds; the final date is anchored to the current book.
