# Assumptions and limitations

## Regulatory basis

The regulatory configuration is based on Basel MAR20 to MAR23 and MAR30 to MAR33 using the consolidated framework snapshot reviewed on 25 August 2026. It represents the Basel global minimum standard. It does not claim to reproduce RBI reporting instructions, national discretions or supervisory model approval.

## Synthetic data

All trades, curves, prices, spreads, volatilities, ratings, RFET observations and notionals are synthetic. The historical data are generated from correlated economic drivers, volatility clustering and stress regimes rather than independent arbitrary draws. Results cannot be interpreted as the capital position of a real institution.

## Pricing scope

Pricing functions are transparent educational models. They generate coherent price, delta, vega and curvature relationships, but do not include production features such as multi-curve bootstrapping, collateral discounting, stochastic volatility, credit calibration, prepayment modelling or front-office model validation.

## Securitisation DRC

Basel maps securitisation DRC risk weights to the banking-book securitisation framework in CRE40 to CRE44 with prescribed modifications. The project applies the SEC-SA formula to explicitly synthetic pool capital ratios and delinquency shares, including the 15% RWA floor and the one-year maturity principle. It does not claim SEC-IRBA or SEC-ERBA calibration.

## Correlations

The engine implements Basel GIRR tenor correlation, CSR factor correlations, equity, commodity and FX correlations, special buckets, and low/medium/high scenario transformations. The CSR cross-bucket matrix is encoded for the standard sector relationships used by the book. Parameter configuration should undergo independent regulatory validation before broader use.

## Curvature

The curvature implementation follows full revaluation, delta removal, separate up/down aggregation and squared correlations. Complex multi-underlying allocation and supervisor-approved alternative FX treatments are outside the synthetic portfolio.

## Model status

This is an educational implementation, not a bank-approved regulatory capital system. Production use would require independent model validation, data lineage controls, jurisdictional legal interpretation, change governance and comprehensive product coverage.

## Internal model representation

The historical model uses single-factor full revaluation for additive model P&L and joint-factor full revaluation for HPL. It applies historical changes to a constant-tenor representation anchored to the valuation snapshot rather than reconstructing every historical front-office curve and contract age. RFET evidence is synthetic and does not demonstrate access to qualifying real transaction data.
