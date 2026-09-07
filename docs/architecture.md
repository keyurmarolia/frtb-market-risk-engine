# Architecture

## Shared calculation foundation

The Standardised Approach and Internal Models Approach reuse trade IDs, desk IDs, pricing functions, risk-factor mapping, valuation market data, issuer attributes and the INR reporting convention.

```text
Trading book + market data
             |
          Pricing
             |
       Risk-factor mapping
          /        \
       SA            IMA
  sensitivities   historical factors
  SBM/DRC/RRAO   RFET/ES/SES/DRC
          \        /
        Desk treatment
             |
     Capital and Market RWA
```

Synthetic economic inputs and Basel regulatory parameters remain stored separately. Every generated input includes a data-status field.

## Calculation grain

Outputs remain available by trade, instrument, desk, factor, modellability status, liquidity horizon, historical date, stress window, ES set, default simulation and capital component. Aggregated totals are calculated from retained detail.

## Desk eligibility

PLA and backtesting are performed at desk level. Green and amber eligible desks enter IMA. Red or non-nominated desks enter one aggregate SA fallback calculation. The full-book SA calculation remains available as the regulatory comparison amount.

## Reporting currency

INR is the reporting currency. USD, EUR and other foreign positions remain in their native trade currency before translation and FX-risk measurement against INR.

## Notebook sequence

The numbered notebooks mirror the calculation order. Each begins with the current calculation, purpose, inputs and output; then shows a numerical example, formula and meaningful visual.
