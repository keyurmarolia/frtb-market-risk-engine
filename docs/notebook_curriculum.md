# Chronological notebook curriculum

## Learning objective

The notebook series provides a complete, linear explanation of how FRTB measures market risk. A calculation is introduced only after its required inputs and economic meaning have been established.

Every calculation notebook follows a simple teaching sequence:

1. State the market-risk question being answered.
2. Identify the trades and risk factors entering the calculation.
3. Explain the regulatory rule in plain language and show the formula.
4. Work through actual trade or factor rows visibly.
5. Run the same calculation across the full synthetic portfolio.
6. Segregate results by product, desk, portfolio, risk class and risk measure where meaningful.
7. Show a chart, flow diagram or correlation matrix that explains the calculation.
8. State what the result means for the next stage.

## Standardised Approach series

### Foundation and economic positions

- `00_project_scope_and_architecture.ipynb`
- `01_synthetic_trading_book.ipynb`
- `02_synthetic_market_data.ipynb`
- `03_pricing_cash_instruments.ipynb`
- `04_pricing_derivatives.ipynb`
- `05_trade_to_risk_factor_mapping.ipynb`

### Delta

- `06_girr_delta.ipynb`
- `07_csr_delta_three_classes.ipynb`
- `08_equity_delta.ipynb`
- `09_fx_delta.ipynb`
- `10_commodity_delta.ipynb`
- `11_exact_risk_factor_netting.ipynb`

### Vega and curvature

- `12_vega_foundation.ipynb`
- `13_rates_derivatives_vega_curvature.ipynb`
- `14_credit_derivatives_vega_curvature.ipynb`
- `15_equity_derivatives_vega_curvature.ipynb`
- `16_fx_derivatives_vega_curvature.ipynb`
- `17_commodity_derivatives_vega_curvature.ipynb`

### SBM capital

- `18_regulatory_weights_and_weighted_sensitivities.ipynb`
- `19_within_bucket_aggregation.ipynb`
- `20_across_bucket_aggregation.ipynb`
- `21_low_medium_high_correlation_scenarios.ipynb`
- `22_seven_class_sbm_result.ipynb`

### Default and residual risk

- `23_drc_non_securitisation.ipynb`
- `24_drc_securitisation_non_ctp.ipynb`
- `25_drc_securitisation_ctp.ipynb`
- `26_rrao.ipynb`

### Final SA view

- `27_desk_and_portfolio_attribution.ipynb`
- `28_frtb_sa_capital_and_market_rwa.ipynb`
- `29_complete_trade_walkthrough.ipynb`

## Internal Models Approach series

### IMA structure and factor eligibility

- `30_ima_complete_calculation_map.ipynb`
- `31_trading_desks_and_ima_risk_factors.ipynb`
- `32_risk_factor_eligibility_test.ipynb`
- `33_liquidity_horizons.ipynb`

### Historical scenarios, ES and NMRFs

- `34_historical_scenarios_and_portfolio_pnl.ipynb`
- `35_nested_liquidity_horizon_expected_shortfall.ipynb`
- `36_full_reduced_current_and_stressed_es.ipynb`
- `37_internal_models_capital_charge.ipynb`
- `38_non_modellable_risk_factor_stress_measure.ipynb`

### Default risk and model performance

- `39_ima_default_risk_charge.ipynb`
- `40_synthetic_daily_desk_history.ipynb`
- `41_hpl_rtpl_and_pnl_attribution.ipynb`
- `42_var_backtesting.ipynb`
- `43_trading_desk_eligibility.ipynb`

### Combined capital and reporting

- `44_ima_capital_aggregation.ipynb`
- `45_combined_sa_ima_capital_and_market_rwa.ipynb`
- `46_reporting_and_calculation_traceability.ipynb`
