"""Build 30 chronological, calculation-led FRTB SA teaching notebooks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"


@dataclass(frozen=True)
class Topic:
    slug: str
    title: str
    objective: str
    context: str
    method: str
    formula: str
    takeaway: str


CHAIN = [
    "Trading book", "Market data", "Pricing", "Risk-factor mapping",
    "Delta / Vega / Curvature", "Exact-factor netting", "Risk weighting",
    "Within buckets", "Across buckets", "Three scenarios", "SBM",
    "DRC + RRAO", "SA capital", "Market RWA",
]


SETUP = """from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yaml
from IPython.display import display
from frtb_engine.notebook_tools import (
    INR_CRORE, bar_crore, bar_inr, configure_notebooks, crore_table,
    draw_capital_map, draw_flow, heatmap, percent_columns,
)

configure_notebooks()
ROOT = Path.cwd()
if not (ROOT / 'outputs').exists():
    ROOT = ROOT.parent
RUN_ID = (ROOT / 'outputs/latest_run.txt').read_text(encoding='utf-8').strip()
RUN = ROOT / 'outputs' / RUN_ID
print(f'Calculation run used in this notebook: {RUN_ID}')"""


TOPICS = [
    Topic("project_scope_and_architecture", "How the complete FRTB SA calculation works",
          "Build a mental map of the entire Standardised Approach before calculating any number.",
          "The Fundamental Review of the Trading Book (FRTB) Standardised Approach (SA) has three capital components. The Sensitivities-based Method (SBM) measures ordinary market movements, the Default Risk Charge (DRC) measures jump-to-default loss, and the Residual Risk Add-on (RRAO) captures specified risks not adequately represented by sensitivities.",
          "One synthetic trading book is priced in Indian rupees (INR). Trades are mapped to factors; sensitivities are calculated by repricing; SBM aggregates them through exact-factor netting, risk weights, buckets and three correlation scenarios. DRC and RRAO are calculated separately and added at the end.",
          r"$$\text{FRTB SA capital}=\text{SBM}+\text{DRC}+\text{RRAO}$$\n\n$$\text{Market RWA}=12.5\times\text{FRTB SA capital}$$",
          "Read the notebooks in number order. Each performs one visible transformation needed by the next stage."),
    Topic("synthetic_trading_book", "Understand the synthetic trading book",
          "Identify what the bank holds before measuring market risk.",
          "A trading book is the collection of positions whose values change with market prices. Every position here is synthetic. Desks and sub-portfolios keep rates, credit, equity, foreign-exchange, commodity and residual-risk positions understandable.",
          "This step checks economic direction, notional, currency, maturity and product type. It does not calculate capital.",
          r"$$\text{Position}=\text{quantity or notional}\times\text{long/short direction}$$",
          "The output is the complete economic inventory that will be priced next."),
    Topic("synthetic_market_data", "Understand the synthetic market data",
          "See which market inputs are needed to price the trading book.",
          "Market data are valuation inputs, not Basel parameters. Curves, credit spreads, equity and commodity spots, foreign-exchange (FX) rates and implied volatilities describe the synthetic market.",
          "Each trade requests its relevant inputs. A foreign bond uses its local rate curve, credit spread and FX rate to translate value into INR.",
          r"$$\text{INR value}=\text{local-currency value}\times\text{INR per unit of local currency}$$",
          "These inputs generate economic prices; regulatory weights remain separately configured."),
    Topic("pricing_cash_instruments", "Price the cash instruments",
          "Calculate local-currency and INR values for bonds, equities and securitisation cash positions.",
          "Cash instruments have direct market values. Foreign positions are first priced locally and then translated to INR, which also creates FX sensitivity.",
          "The local pricing rule depends on the product. The final translation step is common to every foreign position.",
          r"$$V_{INR}=V_{local}\times FX_{local/INR}$$",
          "Every cash instrument has a base INR value for the repricing calculations."),
    Topic("pricing_derivatives", "Price the derivatives",
          "Calculate base INR values for swaps, forwards, options and credit and commodity derivatives.",
          "A derivative derives value from another market variable. Linear products mainly create delta; options also create vega and curvature.",
          "Transparent pricing functions combine trade terms, market inputs and long/short direction, then translate foreign values into INR.",
          r"$$V=\text{pricing model}(\text{trade terms},\text{market inputs})\times\text{direction}$$",
          "These values become the base values used in every sensitivity calculation."),
    Topic("trade_to_risk_factor_mapping", "Map trades to regulatory risk factors",
          "Split each trade into every market factor that can change its INR value.",
          "One trade can create several rows. General Interest Rate Risk (GIRR) captures yield curves, Credit Spread Risk (CSR) captures spreads, and a foreign position also creates FX risk.",
          "Each row keeps the risk class, bucket, exact factor, tenor, curve and location required for exact-factor netting.",
          r"$$\text{Trade}\longrightarrow\{\text{risk class, bucket, factor, tenor, curve, location}\}$$",
          "The portfolio is now granular enough to calculate one-factor-at-a-time sensitivities."),
    Topic("girr_delta", "Calculate General Interest Rate Risk (GIRR) delta",
          "Calculate interest-rate sensitivity by currency and prescribed tenor, including the separate flat inflation and cross-currency basis factors.",
          "Present Value of One Basis Point (PV01) is the value change for a one-basis-point interest-rate movement. One basis point is 0.01 percentage point, or 0.0001 in decimal form. Ordinary yield-curve factors use Basel tenors; inflation and cross-currency basis are flat factors for which tenor is not applicable.",
          "Bump one curve factor, hold everything else constant, reprice the trade and divide the value change by the bump. A cross-currency swap is mapped to both relevant currency curves, its basis factor and FX risk.",
          r"$$s_k=\frac{V(r_k+0.0001)-V(r_k)}{0.0001}$$",
          "GIRR rows remain trade-level and tenor-specific until exact-factor netting."),
    Topic("csr_delta_three_classes", "Calculate Credit Spread Risk (CSR) delta across three classes",
          "Calculate spread sensitivity while keeping the three CSR classes separate.",
          "CS01 is the value change for a one-basis-point credit-spread movement. Non-securitisation, securitisation non-correlation-trading-portfolio (non-CTP), and correlation-trading-portfolio (CTP) remain separate.",
          "Apply a one-basis-point spread bump to one factor and numerically reprice the trade.",
          r"$$s_k=\frac{V(cs_k+0.0001)-V(cs_k)}{0.0001}$$",
          "The identical bump concept produces three distinct regulatory CSR portfolios."),
    Topic("equity_delta", "Calculate equity delta",
          "Calculate equity spot sensitivity for cash, futures, options and index positions.",
          "Equity delta measures the INR value response to the underlying share or index. The bucket is regulatory; the exact factor is the named underlying.",
          "Apply a 1% relative spot bump, reprice, and divide the value change by 0.01.",
          r"$$s_k=\frac{V(S_k\times1.01)-V(S_k)}{0.01}$$",
          "Cash, futures and option deltas can offset only when their complete factor keys match."),
    Topic("fx_delta", "Calculate Foreign Exchange (FX) delta",
          "Calculate currency sensitivity against INR, including FX created by foreign assets.",
          "Foreign Exchange (FX) delta includes dedicated FX products and USD or EUR positions held by other desks.",
          "Apply a 1% relative currency-rate bump, reprice in INR, and divide the value change by 0.01.",
          r"$$s_k=\frac{V(FX_k\times1.01)-V(FX_k)}{0.01}$$",
          "The result shows both direct FX trading and incidental currency risk."),
    Topic("commodity_delta", "Calculate commodity delta",
          "Calculate commodity price sensitivity by commodity, bucket and tenor.",
          "Brent, WTI and gold remain distinct exact factors even when two products share a regulatory bucket.",
          "Apply a 1% relative commodity-price bump, reprice, and divide by 0.01.",
          r"$$s_k=\frac{V(C_k\times1.01)-V(C_k)}{0.01}$$",
          "Commodity identity and tenor remain visible before correlation aggregation."),
    Topic("exact_risk_factor_netting", "Apply exact-risk-factor netting",
          "Offset long and short sensitivities only when complete factor keys are identical.",
          "Sharing a risk class or bucket is not enough. Factor name, tenor, curve, location and other prescribed identifiers must match.",
          "Group trade-level rows by the complete regulatory key and sum their signed sensitivities before applying any risk weight.",
          r"$$s_k=\sum_{i\in\text{same exact factor }k}s_{i,k}$$",
          "The result is one net sensitivity per exact regulatory factor."),
    Topic("vega_foundation", "Calculate vega",
          "Measure how option values respond to a one percentage-point increase in implied volatility.",
          "Vega exists only for optional products. Implied volatility is the market pricing input for expected variability, not the underlying price itself.",
          "Increase implied volatility by 0.01, reprice the option and divide the change by 0.01 to obtain price vega. Multiply price vega by the current implied volatility to obtain the Basel vega sensitivity. Option maturity remains part of factor identity.",
          r"$$\text{Price vega}_k=\frac{V(\sigma_k+0.01)-V(\sigma_k)}{0.01},\qquad s_k^{vega}=\text{Price vega}_k\times\sigma_k$$",
          "Vega remains separate from delta because it measures a different market driver."),
]


def nonlinear_topic(slug: str, title: str, desk: str, products: str) -> Topic:
    return Topic(
        slug, title,
        f"Calculate vega and curvature separately for the {desk.lower()} derivatives portfolio.",
        f"{products} create nonlinear {desk.lower()} exposure. Vega measures volatility risk. Curvature measures loss under larger regulatory up and down shocks after removing the delta contribution.",
        "Price vega uses a one percentage-point volatility bump and is multiplied by current implied volatility for the regulatory sensitivity. Curvature fully reprices under both risk-weight shocks. It is not simply gamma because the regulatory calculation removes the delta effect and aggregates both directions separately.",
        r"$$s^{vega}=\frac{V(\sigma+0.01)-V(\sigma)}{0.01}\times\sigma$$\n\n$$CVR^{up}=-[V(x+RW)-V(x)-RW\times\Delta]$$\n\n$$CVR^{down}=-[V(x-RW)-V(x)+RW\times\Delta]$$",
        "Vega captures volatility risk; curvature captures nonlinear loss missed by a linear delta approximation.",
    )


TOPICS.extend([
    nonlinear_topic("rates_derivatives_vega_curvature", "Rates derivatives: vega and curvature", "Rates", "Swaptions"),
    nonlinear_topic("credit_derivatives_vega_curvature", "Credit derivatives: vega and curvature", "Credit", "Credit options and callable bonds"),
    nonlinear_topic("equity_derivatives_vega_curvature", "Equity derivatives: vega and curvature", "Equity", "Vanilla, index and barrier options"),
    nonlinear_topic("fx_derivatives_vega_curvature", "FX derivatives: vega and curvature", "FX", "USD/INR and EUR/INR options"),
    nonlinear_topic("commodity_derivatives_vega_curvature", "Commodity derivatives: vega and curvature", "Commodity", "Energy and precious-metal options"),
    Topic("regulatory_weights_and_weighted_sensitivities", "Apply Basel risk weights",
          "Convert net sensitivities into weighted sensitivities using regulatory parameters.",
          "A risk weight (RW) belongs to a regulatory risk factor, bucket or tenor rather than simply to an instrument. One bond can therefore receive different GIRR, CSR and FX weights on its separate risk rows. Synthetic market data generate sensitivity; Basel configuration supplies the weight.",
          "First review the complete delta and vega schedules. Then multiply each exact-factor net sensitivity by its applicable weight. Curvature is different: the delta risk weight defines the up and down revaluation shock and is not multiplied a second time.",
          r"$$WS_k=RW_k\times s_k$$",
          "Weighted sensitivities can now be combined using prescribed correlations."),
    Topic("within_bucket_aggregation", "Aggregate sensitivities within each bucket",
          "Calculate the bucket capital amount Kb from weighted sensitivities.",
          "Kb combines factors using within-bucket correlation rho. The initial Sb is the uncapped signed sum used across buckets. Only if the across-bucket radicand becomes negative is the alternative capped Sb between minus Kb and plus Kb applied. For GIRR, inflation-to-yield correlation is 40%; cross-currency basis has 0% correlation with yield, inflation and other basis curves.",
          "Add squared weighted sensitivities and every correlated pair contribution, then take the square root.",
          r"$$K_b=\sqrt{\sum_kWS_k^2+\sum_k\sum_{l\ne k}\rho_{kl}WS_kWS_l}$$\n\n$$S_b=\sum_kWS_k;\quad S_b^{alt}=\max[-K_b,\min(S_b,K_b)]\text{ only when required}$$",
          "Each bucket is now represented by Kb and Sb rather than many factor rows."),
    Topic("across_bucket_aggregation", "Aggregate across buckets",
          "Combine bucket Kb and Sb amounts into one capital amount for each risk class.",
          "Across-bucket correlation gamma permits only the diversification prescribed between different regulatory buckets.",
          "Use the same square-root structure, now with bucket results instead of individual factors.",
          r"$$K_{class}=\sqrt{\sum_bK_b^2+\sum_b\sum_{c\ne b}\gamma_{bc}S_bS_c}$$",
          "This produces one result for every scenario, risk class and sensitivity measure."),
    Topic("low_medium_high_correlation_scenarios", "Compare the three correlation scenarios",
          "Run complete SBM under low, medium and high correlations and select the largest result.",
          "Changing correlation can raise or lower capital depending on hedges. Sensitivities and risk weights stay unchanged; only correlations are transformed.",
          "Recalculate all seven classes and all three measures under each scenario, then select the largest total.",
          r"$$SBM=\max(SBM_{low},SBM_{medium},SBM_{high})$$",
          "Only the largest scenario total enters final FRTB SA capital."),
    Topic("seven_class_sbm_result", "View the seven-class SBM result",
          "Show delta, vega and curvature across all seven formal SBM risk classes.",
          "The three CSR classes remain separate. A zero means no applicable charge for that measure in this synthetic book, not removal of the class.",
          "Add the selected scenario's 21 risk-class-by-measure capital cells to obtain total SBM.",
          r"$$SBM_{scenario}=\sum_{class}(K^{delta}+K^{vega}+K^{curvature})$$",
          "This completes SBM; default and residual risk are calculated separately."),
])


def drc_topic(slug: str, title: str, description: str) -> Topic:
    return Topic(
        slug, title,
        "Follow the complete path from gross jump-to-default exposure to DRC capital.",
        description + " Jump to Default (JTD) is the loss or gain if a reference name defaults immediately. The Hedge Benefit Ratio (HBR) limits short-position offset.",
        "Calculate gross JTD trade by trade, apply permitted netting, separate net long and short JTD, risk-weight both sides, and discount the short-side benefit through HBR.",
        r"$$HBR=\frac{\text{net long JTD}}{\text{net long JTD}+|\text{net short JTD}|}$$\n\n$$DRC_b=\text{weighted long}-HBR\times|\text{weighted short}|$$",
        "The charge remains separate from the other DRC classes and from CSR spread risk in SBM.",
    )


TOPICS.extend([
    drc_topic("drc_non_securitisation", "Default Risk Charge (DRC) for non-securitisations", "Ordinary bonds, credit default swaps (CDS) and equities use seniority, loss-given-default and maturity information."),
    drc_topic("drc_securitisation_non_ctp", "Default Risk Charge (DRC) for securitisations outside CTP", "Securitisation positions outside the correlation trading portfolio use separate tranche treatment."),
    drc_topic("drc_securitisation_ctp", "Default Risk Charge (DRC) for the correlation trading portfolio", "CTP tranches and eligible index hedges use their own aggregation and cross-index treatment."),
    Topic("rrao", "Calculate the Residual Risk Add-on",
          "Classify qualifying residual risks and apply the charge to gross notional without netting.",
          "The Residual Risk Add-on (RRAO) is additional to SBM and DRC. Exotic underlyings use 1.0%; other residual risks use 0.1%. Long and short trades do not offset.",
          "Translate gross notional to INR and multiply it by the applicable residual-risk weight.",
          r"$$RRAO_i=|\text{gross notional}_{i,INR}|\times RW_i$$",
          "RRAO is added without diversification against SBM or DRC."),
    Topic("desk_and_portfolio_attribution", "Understand desk and portfolio exposures",
          "Compare meaningful pre-aggregation risk indicators across desks and sub-portfolios.",
          "SBM capital is not fully additive by desk because netting and correlation are portfolio-level. Actual INR bump effects show where exposure originates without presenting a false capital allocation.",
          "For each delta and vega row, calculate shocked value minus base value, then show gross and signed effects by desk.",
          r"$$\text{bump effect}=V_{shocked}-V_{base}$$",
          "This explains the source of risk while preserving portfolio-level regulatory aggregation."),
    Topic("frtb_sa_capital_and_market_rwa", "Calculate total FRTB SA capital and market RWA",
          "Add SBM, the three DRC charges and RRAO, then convert capital to market risk-weighted assets.",
          "Risk-weighted assets (RWA) express capital on the Basel 8% capital-ratio scale. The factor 12.5 is the inverse of 8%.",
          "Add the components without diversification, then multiply total capital by 12.5.",
          r"$$\text{SA capital}=\text{SBM}+\text{DRC}+\text{RRAO}$$\n\n$$\text{Market RWA}=12.5\times\text{SA capital}$$",
          "This is the end-to-end Standardised Approach result for the synthetic portfolio."),
    Topic("complete_trade_walkthrough", "Trace one trade through the complete calculation",
          "Follow corporate bond C02 from trade terms through pricing, sensitivities and default risk.",
          "One foreign corporate bond creates GIRR, CSR and FX sensitivities in SBM and jump-to-default exposure in DRC. The trade identifier links every stage.",
          "Display each stage separately so unlike columns are not forced into one unreadable table.",
          r"$$C02\rightarrow\text{price}\rightarrow\{GIRR,CSR,FX\}\rightarrow SBM$$\n\n$$C02\rightarrow JTD\rightarrow DRC$$",
          "Every portfolio result can be traced back to identifiable trades, inputs and transformations."),
])


def calculation_code(number: int) -> str:
    if number == 0:
        return """summary=json.loads((RUN/'16_capital_summary.json').read_text())
classes=['GIRR','CSR non-securitisation','CSR securitisation non-CTP',
         'CSR securitisation CTP','Equity','Commodity','FX']
print('The seven SBM risk classes are:')
for position,name in enumerate(classes,1): print(f'{position}. {name}')
print()
print(f"Synthetic trades: {summary['synthetic_trade_count']}")
print(f"Reporting currency: {summary['reporting_currency']}")"""
    if number == 1:
        return """trades=pd.read_csv(RUN/'01_trades.csv')
shown=trades[['trade_id','desk','sub_portfolio','instrument_type','product_form','currency',
              'notional','long_short','underlying','maturity_years','is_synthetic']].copy()
shown['notional']=shown['notional']/INR_CRORE
shown=shown.rename(columns={'notional':'Notional in trade currency (crore)'})
display(shown)
portfolio_map=trades.groupby(['desk','product_form']).size().unstack(fill_value=0)
display(portfolio_map)"""
    if number == 2:
        return """market=yaml.safe_load((ROOT/'data/synthetic/market_data.yaml').read_text())
rows=[]
for group,values in market.items():
    if isinstance(values,dict):
        for key,value in values.items():
            if isinstance(value,dict):
                for tenor,amount in value.items(): rows.append([group,key,tenor,amount])
            else: rows.append([group,key,'',value])
inputs=pd.DataFrame(rows,columns=['market_group','risk_factor','tenor','value'])
display(inputs.head(40))
rates=inputs[inputs.market_group=='rates'].copy()
rates['tenor_number']=pd.to_numeric(rates.tenor)"""
    if number in (3, 4):
        form = "cash" if number == 3 else "derivative"
        return f"""values=pd.read_csv(RUN/'02_valuations.csv')
view=values[values.product_form=={form!r}].copy()
view['calculated_inr']=view.market_value_local*view.fx_to_inr
columns=['trade_id','desk','instrument_type','currency','market_value_local','fx_to_inr','market_value_inr']
display(crore_table(view[columns],['market_value_inr']))
example=view[view.currency!='INR'].iloc[0]
print(f"Worked trade {{example.trade_id}}: {{example.market_value_local:,.2f}} {{example.currency}} x {{example.fx_to_inr:,.4f}} = INR {{example.market_value_inr:,.2f}}")"""
    if number == 5:
        return """mapping=pd.read_csv(RUN/'03_delta_trade_level.csv')
mapping['tenor_display']=mapping.apply(
    lambda row:f"{row.tenor:g} years" if pd.notna(row.tenor)
    else 'Not applicable for this risk factor',axis=1)
columns=['trade_id','desk','instrument_type','currency','risk_class','bucket','risk_factor_id','tenor_display','market_group']
display(mapping[columns].head(35))
print('One foreign corporate bond becomes these separate rows:')
display(mapping[mapping.trade_id=='C02'][columns])
counts=mapping.groupby(['trade_id','instrument_type']).size().rename('number_of_risk_factors').reset_index()
display(counts.sort_values('number_of_risk_factors',ascending=False).head(12))"""
    if number == 6:
        return """from frtb_engine.parameters import risk_weight
delta=pd.read_csv(RUN/'03_delta_trade_level.csv')
view=delta[delta.risk_class=='GIRR'].copy()
view['value_change_for_bump_inr']=view.shocked_value_inr-view.base_value_inr
view['applicable_risk_weight']=view.apply(lambda row:risk_weight(row.to_dict(),'DELTA'),axis=1)
view['tenor_display']=view.apply(
    lambda row: f"{row.tenor:g} years" if row.factor_type=='standard'
    else ('Not applicable — flat inflation factor' if row.factor_type=='inflation'
          else 'Not applicable — flat cross-currency basis factor'),axis=1)
view['factor_label']=view.apply(
    lambda row: f"{row.bucket} OIS — {row.tenor:g}Y" if row.factor_type=='standard'
    else (f"{row.bucket} inflation — flat" if row.factor_type=='inflation'
          else f"{row.risk_factor_id.replace('_',' ')} — flat"),axis=1)
columns=['trade_id','instrument_type','currency','bucket','risk_factor_id','factor_type','tenor_display',
         'applicable_risk_weight','base_value_inr','shocked_value_inr','value_change_for_bump_inr','raw_sensitivity']
shown=crore_table(view[columns],['base_value_inr','shocked_value_inr','value_change_for_bump_inr','raw_sensitivity'])
display(percent_columns(shown,['applicable_risk_weight']).head(30))
print('The risk weight is shown for reference. Formal weighting happens after exact-factor netting in Notebook 18.')
example=view.iloc[0]
print()
print(f"Worked trade: {example.trade_id} | factor: {example.risk_factor_id}")
print(f"Base value: INR {example.base_value_inr/INR_CRORE:,.4f} crore")
print(f"Shocked value: INR {example.shocked_value_inr/INR_CRORE:,.4f} crore")
print(f"Value change for +1 bp: INR {example.value_change_for_bump_inr:,.2f}")
print(f"Sensitivity = value change / 0.0001 = INR {example.raw_sensitivity:,.2f} per unit rate change")"""
    if 7 <= number <= 10:
        risk_class = {6:"GIRR",7:"CSR",8:"EQUITY",9:"FX",10:"COMMODITY"}[number]
        condition = "view=delta[delta.risk_class.str.startswith('CSR')].copy()" if number == 7 else f"view=delta[delta.risk_class=='{risk_class}'].copy()"
        return f"""from frtb_engine.parameters import risk_weight
delta=pd.read_csv(RUN/'03_delta_trade_level.csv')
{condition}
view['value_change_for_bump_inr']=view.shocked_value_inr-view.base_value_inr
view['bump_unit']=np.where(view.relative,'1% relative move','1 basis point')
view['applicable_risk_weight']=view.apply(lambda row:risk_weight(row.to_dict(),'DELTA'),axis=1)
view['tenor_display']=view.apply(
    lambda row:f"{{row.tenor:g}} years" if pd.notna(row.tenor)
    else 'Not applicable for this risk factor',axis=1)
columns=['trade_id','instrument_type','currency','risk_class','bucket','risk_factor_id','tenor_display',
         'bump_unit','applicable_risk_weight','base_value_inr','shocked_value_inr','value_change_for_bump_inr','raw_sensitivity']
shown=crore_table(view[columns],['base_value_inr','shocked_value_inr','value_change_for_bump_inr','raw_sensitivity'])
display(percent_columns(shown,['applicable_risk_weight']).head(25))
print('The risk weight is shown for reference. Formal weighting happens after exact-factor netting in Notebook 18.')
example=view.iloc[0]
print(f"Worked trade: {{example.trade_id}} | factor: {{example.risk_factor_id}}")
print(f"Base value: INR {{example.base_value_inr/INR_CRORE:,.4f}} crore")
print(f"Shocked value: INR {{example.shocked_value_inr/INR_CRORE:,.4f}} crore")
print(f"Value change for bump: INR {{example.value_change_for_bump_inr:,.2f}}")
print(f"Sensitivity = value change / bump = INR {{example.raw_sensitivity:,.2f}} per unit change")"""
    if number == 11:
        return """trade_delta=pd.read_csv(RUN/'03_delta_trade_level.csv')
netted=pd.read_csv(RUN/'06_delta_netted_weighted.csv')
counts=trade_delta.groupby('risk_factor_id').size().sort_values(ascending=False)
factor=counts[counts>1].index[0]
before=trade_delta[trade_delta.risk_factor_id==factor][['trade_id','risk_class','bucket','risk_factor_id','tenor','raw_sensitivity']]
after=netted[netted.risk_factor_id==factor][['risk_class','bucket','risk_factor_id','tenor','raw_sensitivity']]
before['tenor_display']=before.tenor.apply(lambda value:f"{value:g} years" if pd.notna(value) else 'Not applicable for this risk factor')
after['tenor_display']=after.tenor.apply(lambda value:f"{value:g} years" if pd.notna(value) else 'Not applicable for this risk factor')
print(f'Worked exact factor: {factor}')
display(crore_table(before.drop(columns='tenor'),['raw_sensitivity']))
display(crore_table(after.drop(columns='tenor'),['raw_sensitivity']))
print(f"Trade-level signed sum: INR {before.raw_sensitivity.sum():,.2f} per unit change")
print(f"Netted factor sensitivity: INR {after.raw_sensitivity.sum():,.2f} per unit change")"""
    if number == 12:
        return """from frtb_engine.parameters import risk_weight
vega=pd.read_csv(RUN/'04_vega_trade_level.csv')
vega['one_vol_point_change_inr']=vega.shocked_value_inr-vega.base_value_inr
vega['applicable_risk_weight']=vega.apply(lambda row:risk_weight(row.to_dict(),'VEGA'),axis=1)
columns=['trade_id','desk','instrument_type','risk_class','risk_factor_id','tenor',
         'applicable_risk_weight','base_value_inr','shocked_value_inr','one_vol_point_change_inr','raw_sensitivity']
shown=crore_table(vega[columns],['base_value_inr','shocked_value_inr','one_vol_point_change_inr','raw_sensitivity'])
display(percent_columns(shown,['applicable_risk_weight']))
print('The vega risk weight is shown for reference and is applied after exact-factor netting in Notebook 18.')
example=vega.iloc[0]
print(f"Worked trade {example.trade_id}: INR {example.one_vol_point_change_inr:,.2f} change for one volatility percentage point")"""
    if 13 <= number <= 17:
        desk={13:"Rates",14:"Credit",15:"Equity",16:"FX",17:"Commodity"}[number]
        return f"""from frtb_engine.parameters import risk_weight
vega=pd.read_csv(RUN/'04_vega_trade_level.csv')
curvature=pd.read_csv(RUN/'05_curvature_trade_level.csv')
desk_vega=vega[vega.desk=={desk!r}].copy()
desk_curvature=curvature[curvature.desk=={desk!r}].copy()
desk_vega['one_vol_point_change_inr']=desk_vega.shocked_value_inr-desk_vega.base_value_inr
desk_vega['applicable_risk_weight']=desk_vega.apply(lambda row:risk_weight(row.to_dict(),'VEGA'),axis=1)
print('Vega rows')
vega_shown=crore_table(desk_vega[['trade_id','instrument_type','risk_class','risk_factor_id','applicable_risk_weight','one_vol_point_change_inr','raw_sensitivity']],['one_vol_point_change_inr','raw_sensitivity'])
display(percent_columns(vega_shown,['applicable_risk_weight']))
print('Curvature rows')
columns=['trade_id','instrument_type','risk_class','risk_factor_id','shock_size','base_value_inr',
         'shocked_value_inr','down_value_inr','curvature_up','curvature_down','raw_sensitivity']
display(percent_columns(crore_table(desk_curvature[columns],['base_value_inr','shocked_value_inr','down_value_inr','curvature_up','curvature_down','raw_sensitivity']),['shock_size']))"""
    if number == 18:
        return """from frtb_engine.config import load_sbm_parameters
params=load_sbm_parameters(); delta_rw=params['delta_risk_weights']; schedules=[]
girr_rows=[{'risk_class':'GIRR','factor_or_bucket':f'{tenor:g}Y tenor','risk_weight':weight} for tenor,weight in delta_rw['GIRR']['tenors'].items()]
girr_rows += [{'risk_class':'GIRR','factor_or_bucket':'Inflation — flat factor','risk_weight':delta_rw['GIRR']['inflation']},
              {'risk_class':'GIRR','factor_or_bucket':'Cross-currency basis — flat factor','risk_weight':delta_rw['GIRR']['cross_currency_basis']}]
schedules.extend(girr_rows)
for risk_class in ['CSR_NON_SECURITISATION','CSR_SECURITISATION_CTP']:
    schedules.extend({'risk_class':risk_class,'factor_or_bucket':f'Bucket {bucket}','risk_weight':weight}
                     for bucket,weight in delta_rw[risk_class]['buckets'].items())
nonctp=delta_rw['CSR_SECURITISATION_NON_CTP']
for bucket,base in nonctp['base_buckets_1_to_8'].items():
    schedules.append({'risk_class':'CSR_SECURITISATION_NON_CTP','factor_or_bucket':f'Bucket {bucket} — senior IG','risk_weight':base})
    schedules.append({'risk_class':'CSR_SECURITISATION_NON_CTP','factor_or_bucket':f'Bucket {bucket+8} — non-senior IG','risk_weight':base*nonctp['non_senior_ig_multiplier']})
    schedules.append({'risk_class':'CSR_SECURITISATION_NON_CTP','factor_or_bucket':f'Bucket {bucket+16} — high yield','risk_weight':base*nonctp['high_yield_multiplier']})
schedules.append({'risk_class':'CSR_SECURITISATION_NON_CTP','factor_or_bucket':'Bucket 25 — other','risk_weight':nonctp['other_bucket_25']})
for risk_class,key in [('EQUITY','spot_buckets'),('COMMODITY','buckets')]:
    schedules.extend({'risk_class':risk_class,'factor_or_bucket':f'Bucket {bucket}','risk_weight':weight}
                     for bucket,weight in delta_rw[risk_class][key].items())
schedules.append({'risk_class':'FX','factor_or_bucket':'All currency pairs','risk_weight':delta_rw['FX']['all_pairs']})
delta_schedule=pd.DataFrame(schedules)
print('Complete delta risk-weight schedule')
for risk_class,data in delta_schedule.groupby('risk_class',sort=False):
    print(risk_class.replace('_',' ')); display(percent_columns(data[['factor_or_bucket','risk_weight']],['risk_weight']))
vega_schedule=pd.DataFrame([{'risk_class':key.replace('_',' '),'risk_weight':value}
                            for key,value in params['vega_risk_weights'].items() if key!='source'])
print('Complete vega risk-weight schedule')
display(percent_columns(vega_schedule,['risk_weight']))

weighted=pd.concat([pd.read_csv(RUN/'06_delta_netted_weighted.csv'),pd.read_csv(RUN/'07_vega_netted_weighted.csv')],ignore_index=True)
weighted['calculated_weighted']=weighted.raw_sensitivity*weighted.risk_weight
columns=['risk_measure','risk_class','bucket','risk_factor_id','raw_sensitivity','risk_weight','weighted_sensitivity']
shown=crore_table(weighted[columns],['raw_sensitivity','weighted_sensitivity'])
display(percent_columns(shown,['risk_weight']).head(30))
example=weighted.iloc[0]
print(f"Worked factor {example.risk_factor_id}: {example.raw_sensitivity:,.2f} x {example.risk_weight*100:,.2f}% = {example.weighted_sensitivity:,.2f}")"""
    if number == 19:
        return """from frtb_engine.parameters import within_bucket_correlation
weighted=pd.read_csv(RUN/'06_delta_netted_weighted.csv')
girr=weighted[weighted.risk_class=='GIRR']
groups=girr.groupby(['risk_class','bucket']).size().sort_values(ascending=False)
risk_class,bucket=groups[groups>=2].index[0]
sample=weighted[(weighted.risk_class==risk_class)&(weighted.bucket.astype(str)==str(bucket))].copy()
records=sample.to_dict('records'); matrix=np.eye(len(records))
for i,left in enumerate(records):
    for j,right in enumerate(records):
        if i!=j: matrix[i,j]=within_bucket_correlation(left,right,'medium')
corr=pd.DataFrame(matrix,index=sample.risk_factor_id,columns=sample.risk_factor_id)
variance=sum(row['weighted_sensitivity']**2 for row in records)
for i,left in enumerate(records):
    for right in records[i+1:]:
        variance+=2*within_bucket_correlation(left,right,'medium')*left['weighted_sensitivity']*right['weighted_sensitivity']
kb=np.sqrt(max(variance,0)); sb=max(min(sample.weighted_sensitivity.sum(),kb),-kb)
sample['tenor_display']=sample.apply(
    lambda row:f"{row.tenor:g} years" if row.factor_type=='standard'
    else 'Not applicable — flat factor',axis=1)
display(crore_table(sample[['risk_factor_id','factor_type','tenor_display','weighted_sensitivity']],['weighted_sensitivity']))
print(f'Selected bucket: {risk_class} / {bucket}')
print(f'Kb = INR {kb/INR_CRORE:,.4f} crore')
print(f'Sb = INR {sb/INR_CRORE:,.4f} crore')"""
    if number == 20:
        return """from frtb_engine.parameters import cross_bucket_correlation
buckets=pd.read_csv(RUN/'08_sbm_bucket_results.csv')
sample=buckets[(buckets.scenario=='medium')&(buckets.risk_measure=='DELTA')&(buckets.risk_class=='GIRR')].dropna(subset=['k_bucket']).copy()
records=sample.to_dict('records'); variance=sum(row['k_bucket']**2 for row in records); pairs=[]
for i,left in enumerate(records):
    for right in records[i+1:]:
        gamma=cross_bucket_correlation('GIRR',str(left['bucket']),str(right['bucket']),'medium')
        variance+=2*gamma*left['s_bucket']*right['s_bucket']
        pairs.append({'bucket 1':left['bucket'],'bucket 2':right['bucket'],'gamma':gamma})
display(crore_table(sample[['bucket','k_bucket','s_bucket']],['k_bucket','s_bucket']))
display(percent_columns(pd.DataFrame(pairs).head(12),['gamma']))
print(f"GIRR delta capital: INR {np.sqrt(max(variance,0))/INR_CRORE:,.4f} crore")"""
    if number == 21:
        return """scenarios=pd.read_csv(RUN/'10_sbm_scenarios.csv')
scenarios['SBM capital (INR crore)']=scenarios.sbm_capital/INR_CRORE
scenarios['selected']=scenarios.sbm_capital==scenarios.sbm_capital.max()
display(scenarios[['scenario','SBM capital (INR crore)','selected']])
selected=scenarios.loc[scenarios.sbm_capital.idxmax()]
print(f"Selected scenario: {selected.scenario} | INR {selected.sbm_capital/INR_CRORE:,.4f} crore")"""
    if number == 22:
        return """classes=pd.read_csv(RUN/'09_sbm_class_results.csv')
scenarios=pd.read_csv(RUN/'10_sbm_scenarios.csv')
selected=scenarios.loc[scenarios.sbm_capital.idxmax(),'scenario']
view=classes[classes.scenario==selected].copy()
pivot=view.pivot(index='risk_class',columns='risk_measure',values='capital').fillna(0)/INR_CRORE
display(pivot.rename_axis(None).rename_axis(None,axis=1))
print(f'Selected scenario: {selected}')
print(f'Total SBM: INR {view.capital.sum()/INR_CRORE:,.4f} crore')"""
    if 23 <= number <= 25:
        drc_class={23:"NON_SECURITISATION",24:"SECURITISATION_NON_CTP",25:"SECURITISATION_CTP"}[number]
        return f"""gross=pd.read_csv(RUN/'11_drc_gross_jtd.csv'); net=pd.read_csv(RUN/'12_drc_net_jtd.csv'); buckets=pd.read_csv(RUN/'13_drc_bucket_results.csv')
gross_view=gross[gross.drc_class=={drc_class!r}].copy(); net_view=net[net.drc_class=={drc_class!r}].copy(); bucket_view=buckets[buckets.drc_class=={drc_class!r}].copy()
gross_view=gross_view.dropna(axis=1,how='all'); net_view=net_view.dropna(axis=1,how='all'); bucket_view=bucket_view.dropna(axis=1,how='all')
print('1. Gross trade-level JTD'); display(percent_columns(crore_table(gross_view,['gross_jtd']),['risk_weight']).fillna('Not applicable'))
print('2. Net JTD after permitted offsetting'); display(percent_columns(crore_table(net_view,['net_jtd']),['risk_weight']).fillna('Not applicable'))
print('3. HBR and risk-weighted bucket charge'); display(crore_table(bucket_view,['net_long_jtd','net_short_jtd','weighted_long','weighted_short','capital']))
print(f"Capital for this DRC class: INR {{bucket_view.capital.sum()/INR_CRORE:,.4f}} crore")"""
    if number == 26:
        return """detail=pd.read_csv(RUN/'15_rrao_detail.csv')
columns=['trade_id','desk','instrument_type','rrao_type','classification_reason','gross_notional_inr','risk_weight','rrao_charge']
display(percent_columns(crore_table(detail[columns],['gross_notional_inr','rrao_charge']),['risk_weight']))
print(f"Total RRAO: INR {detail.rrao_charge.sum()/INR_CRORE:,.4f} crore")"""
    if number == 27:
        return """delta=pd.read_csv(RUN/'03_delta_trade_level.csv'); vega=pd.read_csv(RUN/'04_vega_trade_level.csv')
effects=pd.concat([delta.assign(measure='Delta'),vega.assign(measure='Vega')],ignore_index=True)
effects['bump_effect_inr']=effects.shocked_value_inr-effects.base_value_inr
desk=effects.groupby(['desk','measure']).agg(signed_effect=('bump_effect_inr','sum'),gross_effect=('bump_effect_inr',lambda x:x.abs().sum())).reset_index()
display(crore_table(desk,['signed_effect','gross_effect']))
portfolio=effects.groupby(['desk','sub_portfolio','risk_class'])['bump_effect_inr'].apply(lambda x:x.abs().sum()).reset_index()
display(crore_table(portfolio,['bump_effect_inr']).head(30))"""
    if number == 28:
        return """summary=json.loads((RUN/'16_capital_summary.json').read_text()); drc=pd.read_csv(RUN/'14_drc_summary.csv')
components=pd.DataFrame([
 {'component':'SBM','capital_inr':summary['sbm_capital_inr']},
 {'component':'DRC non-securitisation','capital_inr':drc.loc[drc.drc_class=='NON_SECURITISATION','capital'].iloc[0]},
 {'component':'DRC securitisation non-CTP','capital_inr':drc.loc[drc.drc_class=='SECURITISATION_NON_CTP','capital'].iloc[0]},
 {'component':'DRC securitisation CTP','capital_inr':drc.loc[drc.drc_class=='SECURITISATION_CTP','capital'].iloc[0]},
 {'component':'RRAO','capital_inr':summary['rrao_capital_inr']}])
display(crore_table(components,['capital_inr']))
capital=components.capital_inr.sum()
print(f'Total FRTB SA capital: INR {capital/INR_CRORE:,.4f} crore')
print(f'Market RWA = {capital/INR_CRORE:,.4f} x 12.5 = INR {capital*12.5/INR_CRORE:,.4f} crore')"""
    if number == 29:
        return """trade=pd.read_csv(RUN/'01_trades.csv').query("trade_id=='C02'")
valuation=pd.read_csv(RUN/'02_valuations.csv').query("trade_id=='C02'")
delta=pd.read_csv(RUN/'03_delta_trade_level.csv').query("trade_id=='C02'").copy()
jtd=pd.read_csv(RUN/'11_drc_gross_jtd.csv').query("trade_id=='C02'")
print('1. Original trade terms'); display(trade[['trade_id','desk','instrument_type','currency','notional','long_short','underlying','rating','maturity_years']])
print('2. Base valuation'); display(crore_table(valuation[['trade_id','market_value_local','fx_to_inr','market_value_inr']],['market_value_inr']))
print('3. Separate SBM sensitivity rows'); delta['bump_effect_inr']=delta.shocked_value_inr-delta.base_value_inr
display(crore_table(delta[['risk_class','bucket','risk_factor_id','shock_size','bump_effect_inr','raw_sensitivity']],['bump_effect_inr','raw_sensitivity']))
print('4. DRC gross JTD row')
jtd_display=jtd.dropna(axis=1,how='all').fillna('Not applicable')
display(percent_columns(crore_table(jtd_display,['gross_jtd']),['risk_weight']))"""
    raise ValueError(number)


def visual_code(number: int) -> str:
    if number == 0:
        return "draw_capital_map()"
    if number == 1:
        return """portfolio_map.plot(kind='bar',stacked=True)
plt.title('Synthetic positions by desk and product form',loc='left',weight='bold')
plt.ylabel('Number of trades'); plt.xlabel('Desk'); plt.xticks(rotation=25)
plt.tight_layout(); plt.show()"""
    if number == 2:
        return """for currency,data in rates.groupby('risk_factor'):
    plt.plot(data.tenor_number,data.value*100,marker='o',label=currency)
plt.title('Synthetic interest-rate curves',loc='left',weight='bold')
plt.xlabel('Tenor (years)'); plt.ylabel('Interest rate (%)'); plt.legend(title='Currency')
plt.tight_layout(); plt.show()"""
    if number in (3,4):
        label="Cash-instrument" if number==3 else "Derivative"
        return f"bar_crore(view.groupby('instrument_type')['market_value_inr'].sum(),'{label} market value by product')"
    if number == 5:
        return """links=mapping.groupby(['desk','risk_class']).size().unstack(fill_value=0)
links.plot(kind='bar',stacked=True)
plt.title('Risk-factor rows created by each desk',loc='left',weight='bold')
plt.ylabel('Mapped trade-factor rows'); plt.xlabel('Desk'); plt.xticks(rotation=25)
plt.tight_layout(); plt.show()"""
    if number == 6:
        return """effect=view.groupby('factor_label',dropna=False)['value_change_for_bump_inr'].sum().sort_values()
bar_inr(effect,'Portfolio GIRR value change for a +1 basis-point shock',
        x_axis_label='GIRR factor (currency, curve and tenor)',
        y_axis_label='Signed value change for +1 bp (INR)')"""
    if 7 <= number <= 10:
        grouping={6:"tenor",7:"risk_class",8:"risk_factor_id",9:"bucket",10:"risk_factor_id"}[number]
        return f"bar_inr(view.groupby({grouping!r})['value_change_for_bump_inr'].sum(),'Value change for the calculation bump')"
    if number == 11:
        return """comparison=pd.Series({'Gross absolute sensitivities':before.raw_sensitivity.abs().sum(),
                              'Signed exact-factor net':abs(before.raw_sensitivity.sum())})
bar_crore(comparison,'Selected exposure before and after exact-factor netting')"""
    if number == 12:
        return "bar_inr(vega.groupby('desk')['one_vol_point_change_inr'].sum(),'Option-value change for a one-point volatility increase')"
    if 13 <= number <= 17:
        return """plot_rows=desk_curvature.groupby('trade_id')[['curvature_up','curvature_down']].sum()/INR_CRORE
ax=plot_rows.plot(kind='bar'); ax.set_title('Up and down curvature amounts',loc='left',weight='bold')
ax.set_ylabel('INR crore'); ax.set_xlabel('Trade'); ax.tick_params(axis='x',rotation=0)
plt.tight_layout(); plt.show()"""
    if number == 18:
        return "bar_crore(weighted.groupby('risk_class')['weighted_sensitivity'].apply(lambda x:x.abs().sum()),'Gross absolute weighted sensitivity by risk class')"
    if number == 19:
        return "heatmap(corr,'Medium-scenario within-bucket correlations',value_format='.2f')"
    if number == 20:
        return "bar_crore(sample.set_index('bucket')['k_bucket'],'GIRR standalone bucket capital')"
    if number == 21:
        return "bar_crore(scenarios.set_index('scenario')['sbm_capital'],'SBM capital under the three required scenarios')"
    if number == 22:
        return "heatmap(pivot,'Selected-scenario SBM capital by risk class and measure (INR crore)',value_format=',.2f')"
    if 23 <= number <= 25:
        return """stages=pd.Series({'Gross long JTD':gross_view.loc[gross_view.gross_jtd>0,'gross_jtd'].sum(),
                          'Gross short JTD':abs(gross_view.loc[gross_view.gross_jtd<0,'gross_jtd'].sum()),
                          'Final DRC charge':bucket_view.capital.sum()})
bar_crore(stages,'Default-risk amounts through the calculation')"""
    if number == 26:
        return "bar_crore(detail.groupby('rrao_type')['rrao_charge'].sum(),'RRAO charge by residual-risk type')"
    if number == 27:
        return """plot=desk.pivot(index='desk',columns='measure',values='gross_effect').fillna(0)/INR_CRORE
plot.plot(kind='bar'); plt.title('Gross sensitivity bump effects by desk',loc='left',weight='bold')
plt.ylabel('INR crore'); plt.xlabel('Desk'); plt.xticks(rotation=25)
plt.tight_layout(); plt.show()"""
    if number == 28:
        return "bar_crore(components.set_index('component')['capital_inr'],'Components of total FRTB SA capital')"
    if number == 29:
        return "draw_flow(['C02 trade terms','INR price','GIRR delta','CSR delta','FX delta','Exact-factor netting','SBM','Gross JTD','Net JTD','DRC'],'C02 calculation lineage',wrap_after=5)"
    raise ValueError(number)


def build_notebook(number: int, topic: Topic) -> None:
    notebook=nbf.v4.new_notebook()
    notebook.metadata.kernelspec={"display_name":"Python (FRTB SA Local)","language":"python","name":"frtb-sa-local"}
    notebook.metadata.language_info={"name":"python","version":"3.12"}
    start=max(0,min(number//3,len(CHAIN)-4)); chain_slice=CHAIN[start:start+4]
    notebook.cells=[
        nbf.v4.new_markdown_cell(f"# {number:02d} — {topic.title}\n\n{topic.objective}"),
        nbf.v4.new_markdown_cell(topic.context),
        nbf.v4.new_code_cell(SETUP),
        nbf.v4.new_markdown_cell("This is the part of the calculation chain being handled here:"),
        nbf.v4.new_code_cell(
            f"draw_flow({CHAIN!r},'Complete FRTB Standardised Approach calculation',wrap_after=5)"
            if number==0 else f"draw_flow({chain_slice!r},{topic.title!r},wrap_after=4)"
        ),
        nbf.v4.new_markdown_cell(f"{topic.method}\n\n{topic.formula.replace(chr(92) + 'n', chr(10))}"),
        nbf.v4.new_code_cell(calculation_code(number)),
        nbf.v4.new_markdown_cell("The visual below uses the calculated rows shown above."),
        nbf.v4.new_code_cell(visual_code(number)),
        nbf.v4.new_markdown_cell(topic.takeaway),
    ]
    nbf.write(notebook,NOTEBOOKS/f"{number:02d}_{topic.slug}.ipynb")


def main() -> None:
    if len(TOPICS)!=30:
        raise RuntimeError(f'Expected 30 notebook topics, found {len(TOPICS)}.')
    NOTEBOOKS.mkdir(exist_ok=True)
    for number,topic in enumerate(TOPICS): build_notebook(number,topic)
    print('Built 30 calculation-led teaching notebooks.')


if __name__ == '__main__':
    main()
