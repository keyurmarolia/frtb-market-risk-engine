# Methodology

## Shared pricing and risk factors

Every trade is valued in its native currency and converted to INR. SA sensitivities and IMA factor exposures originate from the same pricing and mapping functions.

## Standardised Approach

GIRR and CSR delta use a one-basis-point absolute bump. Equity, FX and commodity delta use a 1% relative bump. Price vega uses a one-volatility-percentage-point bump; Basel vega sensitivity equals price vega multiplied by current implied volatility. Curvature performs up and down revaluation under the regulatory shock and removes the delta contribution.

Sensitivities net only when their complete regulatory factor keys match. Basel risk weights and within/across-bucket correlations are then applied under low, medium and high scenarios. The maximum seven-class SBM result is selected.

SA DRC is calculated separately for non-securitisations, securitisations non-CTP and securitisations CTP. RRAO applies to gross notional without netting. Full-book SA capital is SBM plus all SA DRC components plus RRAO.

## Synthetic IMA history

The ten-year factor history is deterministic and explicitly synthetic. Correlated rates, credit, equity, FX and commodity drivers are combined with Student-t innovations, volatility clustering and named stress regimes. Final factor levels are anchored to the shared valuation snapshot. Historical scenarios use a constant-tenor representation.

Synthetic RFET observations represent transactions or committed quotes. They are not public closing prices or observed regulatory evidence.

## RFET and liquidity horizons

RFET tests the two Basel routes: at least 24 observations with the 90-day continuity condition, or at least 100 observations over 12 months. Passing factors become MRFs; failing factors become NMRFs.

Factors are mapped to 10, 20, 40, 60 or 120-day regulatory liquidity horizons according to risk class and factor type.

## Expected Shortfall and IMCC

Same-date factor P&L is aggregated into rolling 10-day outcomes. Expected Shortfall is the average loss beyond the 97.5% threshold. Nested factor sets apply the Basel liquidity-horizon square-root formula.

The reduced factor set is selected in descending materiality order within each broad risk class. It must explain at least 75% of full current ES. The most severe 12-month reduced-set window is selected, and stressed ES is scaled by the full-current to reduced-current ratio floored at one.

IMCC is 50% unconstrained all-risk capital plus 50% of the constrained risk-class sum.

## NMRF SES

Each NMRF uses the greater of its regulatory horizon and 20 days. The stress loss is the more conservative of the empirical 97.5% horizon loss and a Student-t volatility estimate. Idiosyncratic credit, idiosyncratic equity and other NMRFs are aggregated separately using the MAR33.17 structure and rho of 0.6 for other NMRFs.

## IMA DRC

Issuer PDs are floored at 0.03%. A global systematic factor and a sector-region systematic factor produce correlated defaults alongside issuer-specific factors. The one-year default-loss distribution uses 250,000 seeded simulations from the synthetic model assumptions. Weekly measures use dated position snapshots and the same calibrated default scenarios. IMA DRC is the greater of current 99.9% VaR and the 12-week average measure.

## PLA and backtesting

Five hundred and one dated position snapshots contain documented resizing and hedge adjustments, with the final date anchored to the current 48-trade book. They produce 500 frozen-prior-day P&L outcomes. HPL uses joint repricing across all mapped factors; RTPL adds single-factor repricing over modellable factors. APL deducts explicit synthetic turnover costs. PLA uses 250 observations, Spearman correlation and the Kolmogorov-Smirnov statistic.

Backtesting forecasts 97.5% and 99% one-day VaR from the preceding 250 observations and compares the forecast at date t with HPL/APL at t+1. No future observation enters the forecast window.

## Combined capital

Eligible green and amber desks enter IMA. Red and non-nominated desks enter one aggregate SA fallback calculation. The non-DRC IMA component is the greater of current IMCC plus SES and multiplier-adjusted 60-day average IMCC plus average SES. IMA DRC is added. The amber coefficient is one half of standalone amber-desk SA divided by standalone green-and-amber SA, and it multiplies the positive difference between eligible-desk SA and eligible-desk IMA.

The coefficient uses the sum of separate eligible-desk SA charges. The positive difference uses SA calculated on the combined eligible portfolio, including diversification. If every desk is ineligible, all IMA components are zero and the final charge equals full-book SA.

The 60-day averaging illustration holds current positions and current stress calibration fixed while moving the observation window. It is a reconstructed current-position comparison, not historical daily capital on the changing portfolio snapshots used for P&L attribution.

```text
Final capital = eligible-desk IMA capital + amber surcharge + SA fallback capital
Market RWA = 12.5 x final capital
```
