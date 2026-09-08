# Data dictionary

## Shared trading book

| Field | Meaning |
|---|---|
| `trade_id` | Unique synthetic position identifier |
| `desk` | Rates, credit, equity, FX, commodity or residual-risk desk |
| `sub_portfolio` | Educational portfolio subdivision |
| `instrument_type` | Pricing and mapping model identifier |
| `product_form` | Cash or derivative |
| `currency` | Native valuation currency |
| `quantity` | Units for share, index or commodity positions |
| `notional` | Contract notional for debt and derivatives |
| `long_short` | Economic default or market-risk direction |
| `underlying` | Exact market or credit risk-factor name |
| `rating` | Synthetic external-equivalent rating category |
| `maturity_years` | Remaining maturity used for pricing and regulatory mapping |
| `option_expiry_years` | Option maturity used for vega mapping |
| `csr_class` | One of the three CSR classes or `NONE` |
| `csr_bucket` | Basel CSR bucket |
| `equity_bucket` | Basel equity bucket |
| `commodity_bucket` | Basel commodity bucket |
| `drc_class` | Non-sec, securitisation non-CTP, CTP or `NONE` |
| `rrao_type` | Exotic underlying, other residual risk or `NONE` |
| `is_synthetic` | Required synthetic-data marker |

## Calculation outputs

The SQLite trade table stores `maturity_years` and `option_expiry_years` as numeric remaining year counts, matching the source trading book.

| Field | Meaning |
|---|---|
| `raw_sensitivity` | Repricing sensitivity before regulatory risk weight |
| `risk_factor_id` | Complete exact-factor netting key |
| `risk_weight` | Versioned Basel parameter |
| `weighted_sensitivity` | Net sensitivity multiplied by risk weight |
| `k_bucket` | Correlated bucket capital |
| `s_bucket` | Directional bucket exposure used across buckets |
| `gross_jtd` | Trade-level jump-to-default exposure |
| `net_jtd` | Permitted obligor or tranche-level net JTD |
| `hbr` | Hedge benefit ratio |
| `rrao_charge` | Gross notional multiplied by the RRAO weight |

## IMA inputs and outputs

| Field | Meaning |
|---|---|
| `data_status` | Explicit synthetic, regulatory or calculated-output classification |
| `daily_change` | Same-date synthetic factor movement in absolute or relative units |
| `market_regime` | Named ordinary or stressed synthetic market regime |
| `qualifying_observation_count` | Unique synthetic RFET evidence dates in the 12-month window |
| `minimum_observations_in_any_90_days` | RFET continuity measure |
| `modellability_status` | MRF or NMRF classification with reason |
| `liquidity_horizon_days` | Basel factor horizon: 10, 20, 40, 60 or 120 days |
| `factor_pnl_inr` | Desk-factor daily P&L contribution in INR |
| `es_10_day_inr` | 97.5% Expected Shortfall before liquidity-horizon adjustment |
| `liquidity_horizon_adjusted_es_inr` | Nested-horizon ES |
| `reduced_set_coverage` | Reduced current ES divided by full current ES |
| `scaled_es_capital_inr` | Reduced stressed ES after the floored scaling ratio |
| `stress_scenario_loss_inr` | Calibrated factor-level NMRF loss |
| `hpl_inr` | Hypothetical P&L from the frozen portfolio and full representation |
| `rtpl_inr` | Risk-Theoretical P&L from the IMA factor representation |
| `apl_inr` | Synthetic Actual P&L used in backtesting |
| `pla_zone` | Green, amber, red or not applicable |
| `final_treatment` | IMA green, IMA amber or SA fallback |
| `ima_drc_capital_inr` | Greater of current 99.9% one-year default VaR and 12-week average |
| `final_frtb_market_risk_capital_inr` | Eligible IMA plus amber surcharge plus SA fallback |
