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

- [00_project_scope_and_architecture.ipynb](../notebooks/00_project_scope_and_architecture.ipynb)
- [01_synthetic_trading_book.ipynb](../notebooks/01_synthetic_trading_book.ipynb)
- [02_synthetic_market_data.ipynb](../notebooks/02_synthetic_market_data.ipynb)
- [03_pricing_cash_instruments.ipynb](../notebooks/03_pricing_cash_instruments.ipynb)
- [04_pricing_derivatives.ipynb](../notebooks/04_pricing_derivatives.ipynb)
- [05_trade_to_risk_factor_mapping.ipynb](../notebooks/05_trade_to_risk_factor_mapping.ipynb)

### Delta

- [06_girr_delta.ipynb](../notebooks/06_girr_delta.ipynb)
- [07_csr_delta_three_classes.ipynb](../notebooks/07_csr_delta_three_classes.ipynb)
- [08_equity_delta.ipynb](../notebooks/08_equity_delta.ipynb)
- [09_fx_delta.ipynb](../notebooks/09_fx_delta.ipynb)
- [10_commodity_delta.ipynb](../notebooks/10_commodity_delta.ipynb)
- [11_exact_risk_factor_netting.ipynb](../notebooks/11_exact_risk_factor_netting.ipynb)

### Vega and curvature

- [12_vega_foundation.ipynb](../notebooks/12_vega_foundation.ipynb)
- [13_rates_derivatives_vega_curvature.ipynb](../notebooks/13_rates_derivatives_vega_curvature.ipynb)
- [14_credit_derivatives_vega_curvature.ipynb](../notebooks/14_credit_derivatives_vega_curvature.ipynb)
- [15_equity_derivatives_vega_curvature.ipynb](../notebooks/15_equity_derivatives_vega_curvature.ipynb)
- [16_fx_derivatives_vega_curvature.ipynb](../notebooks/16_fx_derivatives_vega_curvature.ipynb)
- [17_commodity_derivatives_vega_curvature.ipynb](../notebooks/17_commodity_derivatives_vega_curvature.ipynb)

### SBM capital

- [18_regulatory_weights_and_weighted_sensitivities.ipynb](../notebooks/18_regulatory_weights_and_weighted_sensitivities.ipynb)
- [19_within_bucket_aggregation.ipynb](../notebooks/19_within_bucket_aggregation.ipynb)
- [20_across_bucket_aggregation.ipynb](../notebooks/20_across_bucket_aggregation.ipynb)
- [21_low_medium_high_correlation_scenarios.ipynb](../notebooks/21_low_medium_high_correlation_scenarios.ipynb)
- [22_seven_class_sbm_result.ipynb](../notebooks/22_seven_class_sbm_result.ipynb)

### Default and residual risk

- [23_drc_non_securitisation.ipynb](../notebooks/23_drc_non_securitisation.ipynb)
- [24_drc_securitisation_non_ctp.ipynb](../notebooks/24_drc_securitisation_non_ctp.ipynb)
- [25_drc_securitisation_ctp.ipynb](../notebooks/25_drc_securitisation_ctp.ipynb)
- [26_rrao.ipynb](../notebooks/26_rrao.ipynb)

### Final SA view

- [27_desk_and_portfolio_attribution.ipynb](../notebooks/27_desk_and_portfolio_attribution.ipynb)
- [28_frtb_sa_capital_and_market_rwa.ipynb](../notebooks/28_frtb_sa_capital_and_market_rwa.ipynb)
- [29_complete_trade_walkthrough.ipynb](../notebooks/29_complete_trade_walkthrough.ipynb)

## Internal Models Approach series

### IMA structure and factor eligibility

- [30_ima_complete_calculation_map.ipynb](../notebooks/30_ima_complete_calculation_map.ipynb)
- [31_trading_desks_and_ima_risk_factors.ipynb](../notebooks/31_trading_desks_and_ima_risk_factors.ipynb)
- [32_risk_factor_eligibility_test.ipynb](../notebooks/32_risk_factor_eligibility_test.ipynb)
- [33_liquidity_horizons.ipynb](../notebooks/33_liquidity_horizons.ipynb)

### Historical scenarios, ES and NMRFs

- [34_historical_scenarios_and_portfolio_pnl.ipynb](../notebooks/34_historical_scenarios_and_portfolio_pnl.ipynb)
- [35_nested_liquidity_horizon_expected_shortfall.ipynb](../notebooks/35_nested_liquidity_horizon_expected_shortfall.ipynb)
- [36_full_reduced_current_and_stressed_es.ipynb](../notebooks/36_full_reduced_current_and_stressed_es.ipynb)
- [37_internal_models_capital_charge.ipynb](../notebooks/37_internal_models_capital_charge.ipynb)
- [38_non_modellable_risk_factor_stress_measure.ipynb](../notebooks/38_non_modellable_risk_factor_stress_measure.ipynb)

### Default risk and model performance

- [39_ima_default_risk_charge.ipynb](../notebooks/39_ima_default_risk_charge.ipynb)
- [40_synthetic_daily_desk_history.ipynb](../notebooks/40_synthetic_daily_desk_history.ipynb)
- [41_hpl_rtpl_and_pnl_attribution.ipynb](../notebooks/41_hpl_rtpl_and_pnl_attribution.ipynb)
- [42_var_backtesting.ipynb](../notebooks/42_var_backtesting.ipynb)
- [43_trading_desk_eligibility.ipynb](../notebooks/43_trading_desk_eligibility.ipynb)

### Combined capital and reporting

- [44_ima_capital_aggregation.ipynb](../notebooks/44_ima_capital_aggregation.ipynb)
- [45_combined_sa_ima_capital_and_market_rwa.ipynb](../notebooks/45_combined_sa_ima_capital_and_market_rwa.ipynb)
- [46_reporting_and_calculation_traceability.ipynb](../notebooks/46_reporting_and_calculation_traceability.ipynb)
