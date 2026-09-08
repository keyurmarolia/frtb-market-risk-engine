"""Build the chronological IMA teaching notebooks from retained engine outputs."""

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
    purpose: str
    explanation: str
    inputs: str
    output: str
    norm: str
    formula: str


TOPICS = [
    Topic("ima_complete_calculation_map", "How the complete FRTB Internal Models Approach calculation works",
          "Connect the existing Standardised Approach to the Internal Models Approach using the same trades, prices and risk factors.",
          "The Fundamental Review of the Trading Book (FRTB) uses desk-level model eligibility. Modellable Risk Factors enter Expected Shortfall; Non-Modellable Risk Factors receive a separate stress measure; default risk is simulated independently. Profit and Loss Attribution and backtesting determine which desks may use the model.",
          "The shared 48-trade book, the SA run, the IMA factor inventory and the combined capital summary.",
          "A complete map from trade to final market-risk capital and Market RWA.",
          "Basel norm applied: MAR30–MAR33 require desk approval, RFET, ES, NMRF treatment, IMA DRC, PLA, backtesting and SA fallback.",
          r"$$K_{Market}=C_A+DRC+PLA\ surcharge+C_U,\qquad RWA_{Market}=12.5K_{Market}$$"),
    Topic("trading_desks_and_ima_risk_factors", "Map trading desks and positions to IMA risk factors",
          "Show how the same economic position produces SA sensitivities and an IMA historical risk-factor exposure.",
          "A risk factor is a market variable that changes a position value. Sensitivity is the amount by which value changes when that factor moves. The inventory keeps these two ideas separate and retains trade and desk lineage.",
          "Trade-level delta and vega mappings from the shared pricing and sensitivity engine.",
          "One factor inventory and a desk–trade–factor exposure table.",
          "Basel norm applied: MAR31 requires the internal model to capture all material risk factors used by approved desks.",
          r"$$\Delta V_{i,k}\approx s_{i,k}\,\Delta x_k$$"),
    Topic("risk_factor_eligibility_test", "Apply the Risk Factor Eligibility Test",
          "Determine which IMA factors are Modellable Risk Factors and which are Non-Modellable Risk Factors.",
          "RFET means Risk Factor Eligibility Test. MRF means Modellable Risk Factor. NMRF means Non-Modellable Risk Factor. The observation records here are synthetic transaction and committed-quote events, not public closing prices.",
          "Synthetic qualifying observation dates and the factor inventory.",
          "A factor-level pass or fail, route used and plain-language reason.",
          "Basel norm applied: MAR31.13 permits either 24 observations with continuity or 100 observations over 12 months, with at most one observation per day.",
          r"$$MRF_k=1\{N_k\ge100\ \text{or}\ (N_k\ge24\ \text{and continuity passes})\}$$"),
    Topic("liquidity_horizons", "Assign regulatory liquidity horizons",
          "Map every factor to the time needed to exit or hedge it during stress.",
          "LH means Liquidity Horizon. It is different from instrument maturity. A five-year trade can carry a 10-day rate-factor horizon, while its volatility factor can carry 60 days.",
          "Risk class, factor type, currency, rating, market capitalisation and commodity type.",
          "A documented 10, 20, 40, 60 or 120-day horizon for every factor.",
          "Basel norm applied: MAR33.12 prescribes liquidity-horizon floors by factor category.",
          r"$$LH_k\in\{10,20,40,60,120\}\text{ days}$$"),
    Topic("historical_scenarios_and_portfolio_pnl", "Build joint historical scenarios and portfolio P&L",
          "Convert same-date factor movements into daily desk and portfolio profit or loss.",
          "The synthetic history is not independent random noise. It uses correlated economic drivers, volatility clustering and named stress regimes. Same-date dependence is retained so rates, credit, equity, FX and commodities move together.",
          "Ten years of synthetic regime-aware factor changes and trade-level sensitivities.",
          "Factor, desk and portfolio P&L for each historical date.",
          "Basel norm applied: MAR33 requires a sufficiently long history and joint stressed correlation across relevant factors.",
          r"$$P\&L_t=\sum_k s_k\Delta x_{k,t}+\text{nonlinear repricing effect}_t$$"),
    Topic("nested_liquidity_horizon_expected_shortfall", "Calculate nested liquidity-horizon Expected Shortfall",
          "Measure the average loss beyond the 97.5% loss threshold and apply the five nested liquidity horizons.",
          "ES means Expected Shortfall. The calculation first forms joint 10-day portfolio outcomes. Longer-horizon factors enter nested subsets; standalone factor ES values are not simply added.",
          "Modellable factor P&L, factor liquidity horizons and the selected historical period.",
          "10-day ES, every nested component and liquidity-horizon-adjusted ES.",
          "Basel norm applied: MAR33.3–MAR33.4 use a one-tailed 97.5% ES and 10/20/40/60/120-day nested horizons.",
          r"$$ES^{LH}=\sqrt{ES_{10}^2+\sum_{j=2}^{5}ES_j^2\frac{LH_j-LH_{j-1}}{10}}$$"),
    Topic("full_reduced_current_and_stressed_es", "Calculate full, reduced, current and stressed ES",
          "Identify a reduced modellable factor set, select the most severe 12-month window and scale stressed ES.",
          "F,C means Full Current; R,C means Reduced Current; R,S means Reduced Stress. The same reduced factors are used for current and stress calculations.",
          "Current and historical factor P&L plus the materiality-ranked reduced set.",
          "Full current ES, reduced current ES, reduced stress ES, coverage and the scaled measure.",
          "Basel norm applied: MAR33.5–MAR33.6 require at least 75% reduced-set coverage and floor the scaling ratio at one.",
          r"$$ES_{scaled}=ES_{R,S}^{LH}\max\left(\frac{ES_{F,C}^{LH}}{ES_{R,C}^{LH}},1\right)$$"),
    Topic("internal_models_capital_charge", "Aggregate the Internal Models Capital Charge",
          "Combine unconstrained portfolio ES with constrained risk-class ES.",
          "IMCC means Internal Models Capital Charge. Unconstrained ES recognises empirical dependence across classes. Constrained ES holds other classes constant and limits cross-class diversification.",
          "Scaled ES for the all-risk portfolio and the five broad regulatory risk classes.",
          "The unconstrained component, constrained sum and final IMCC.",
          "Basel norm applied: MAR33.13–MAR33.15 apply equal 50% weights to unconstrained and constrained measures.",
          r"$$IMCC=0.5\,IMCC(C)+0.5\sum_i IMCC(C_i)$$"),
    Topic("non_modellable_risk_factor_stress_measure", "Calculate NMRF stress scenario risk",
          "Capitalise factors that fail RFET using conservative horizon-specific stress losses.",
          "SES means Stress Scenario Risk Measure. Each NMRF uses the greater of its assigned horizon and 20 days. Idiosyncratic credit and equity factors are separated from other NMRFs before aggregation.",
          "NMRF P&L history, liquidity horizons and calibrated stress losses.",
          "Factor stress losses, aggregation categories and final SES.",
          "Basel norm applied: MAR33.16–MAR33.17 calibrate NMRF loss to at least the 97.5% stressed standard and prescribe rho of 0.6 for other NMRFs.",
          r"$$SES=\sqrt{\sum ISES_i^2}+\sqrt{\sum ISES_j^2}+\sqrt{(0.6\sum SES_k)^2+0.64\sum SES_k^2}$$"),
    Topic("ima_default_risk_charge", "Simulate the IMA Default Risk Charge",
          "Measure one-year trading-book default loss at the 99.9% percentile.",
          "PD means Probability of Default and LGD means Loss Given Default. A global factor and a sector-region factor create correlated defaults; issuer-specific shocks retain idiosyncratic risk.",
          "Issuer JTD exposures, ratings, PDs, systematic groups and factor loadings.",
          "A default-loss distribution, 99.9% VaR, tail issuer trace and 12-week capital comparison.",
          "Basel norm applied: MAR33.18–MAR33.39 require a separate one-year, 99.9% default simulation with two systematic factor types and a 0.03% PD floor.",
          r"$$X_i=a_iZ_G+b_iZ_{sector,region}+\sqrt{1-a_i^2-b_i^2}\epsilon_i,\quad Default_i=1\{X_i<\Phi^{-1}(PD_i)\}$$"),
    Topic("synthetic_daily_desk_history", "Build the daily changing desk portfolio",
          "Create the frozen prior-day portfolios required for PLA and backtesting.",
          "The same 48 trades remain the foundation, but their sizes change through documented resizing and hedge adjustments. The final date is anchored to the current book, and fixed seeds make every snapshot reproducible.",
          "The shared trading book and 501 position dates, which produce 500 next-day P&L outcomes.",
          "A date–trade–desk position snapshot with an explicit event reason.",
          "Basel norm applied: MAR32 testing uses daily desk outcomes based on the portfolio held at the relevant date.",
          r"$$P_t=\{q_{1,t},q_{2,t},\ldots,q_{48,t}\}$$"),
    Topic("hpl_rtpl_and_pnl_attribution", "Calculate HPL, RTPL and Profit and Loss Attribution",
          "Compare the full pricing representation with the IMA risk-model representation for the same frozen portfolio.",
          "HPL means Hypothetical Profit and Loss. RTPL means Risk-Theoretical Profit and Loss. PLA means Profit and Loss Attribution. Differences arise from NMRFs, grid simplification, basis effects and nonlinear pricing.",
          "Frozen portfolio snapshots and next-day joint market changes.",
          "Daily HPL and RTPL plus Spearman, KS and green/amber/red classification.",
          "Basel norm applied: MAR32.20–MAR32.44 use 250 observations, Spearman correlation and Kolmogorov-Smirnov distribution separation.",
          r"$$HPL_{t+1}=V(P_t,M_{t+1})-V(P_t,M_t)$$"),
    Topic("var_backtesting", "Backtest one-day Value at Risk",
          "Forecast loss thresholds using only information available at each date and compare them with next-day HPL and APL.",
          "VaR means Value at Risk. APL means Actual Profit and Loss. Backtesting is separate from PLA: it counts threshold exceptions and does not replace ES as the capital measure.",
          "Rolling 250-day P&L histories and next-day desk outcomes.",
          "97.5% and 99% VaR forecasts, dated exceptions and desk pass/fail results.",
          "Basel norm applied: MAR32 requires the forecast-at-t to outcome-at-t+1 sequence and desk tests at 97.5% and 99%.",
          r"$$Exception_{t+1}=1\{-P\&L_{t+1}>VaR_t\}$$"),
    Topic("trading_desk_eligibility", "Determine desk eligibility for IMA",
          "Combine PLA, backtesting and desk nomination to select IMA or SA treatment.",
          "A green desk can use IMA when backtesting passes. An amber desk remains eligible with the applicable surcharge. A red or non-nominated desk falls back to SA.",
          "PLA zones, backtesting results and desk model scope.",
          "A reasoned treatment for every trading desk.",
          "Basel norm applied: MAR30 and MAR32 apply model approval and ongoing testing at trading-desk level.",
          r"$$Treatment_d=f(PLA_d,Backtesting_d,Model\ scope_d)$$"),
    Topic("ima_capital_aggregation", "Aggregate IMA capital for eligible desks",
          "Apply current-versus-average rules, the backtesting multiplier, IMA DRC and the amber surcharge.",
          "The non-DRC component compares current IMCC plus SES with multiplier-adjusted 60-day average IMCC plus average SES. This notebook reconstructs the 60-day comparison at current positions and stress calibration; it is not capital measured on each day's historical holdings. IMA DRC compares current with its 12-week average.",
          "IMCC and SES histories, bank-wide exceptions, IMA DRC and amber-desk SA comparison.",
          "Eligible-desk IMA capital with every component shown separately.",
          "Basel norm applied: MAR33.22 and MAR33.41–MAR33.45 prescribe the averaging, multiplier and amber-surcharge treatment.",
          r"$$C_A=\max(IMCC_t+SES_t,\ m_c\overline{IMCC}_{60}+\overline{SES}_{60})$$"),
    Topic("combined_sa_ima_capital_and_market_rwa", "Combine IMA and SA fallback into final Market RWA",
          "Join eligible IMA desks and ineligible SA desks without counting a position twice.",
          "The full-book SA result remains visible for comparison. Only the aggregate SA charge for fallback desks enters final capital alongside eligible-desk IMA capital and any amber surcharge.",
          "IMA eligible capital, amber surcharge, SA fallback capital and full-book SA benchmark.",
          "Final FRTB market-risk capital and Market RWA in INR.",
          "Basel norm applied: MAR33.43 aggregates eligible IMA desks with SA fallback; MAR33.46 multiplies capital by 12.5.",
          r"$$K_{Market}=IMA_{G,A}+PLA\ surcharge+C_U,\qquad RWA_{Market}=12.5K_{Market}$$"),
    Topic("reporting_and_calculation_traceability", "Trace the combined FRTB calculation from capital to trades",
          "Make every reported amount traceable through desks, model stages, factors and positions.",
          "The reporting layer does not create capital. It presents retained calculation outputs from the same run in a compact form.",
          "The combined capital summary, desk results, IMCC stages, NMRFs, default tail simulations and run manifest.",
          "A capital summary and drill-down map suitable for the reporting workbook and repository outputs.",
          "Basel norm applied: MAR30 model validation expects transparent and accessible data flows, model inputs and calculations.",
          r"$$Capital\rightarrow Desk\rightarrow Measure\rightarrow Scenario\rightarrow Factor\rightarrow Trade$$"),
]


SETUP = """from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display
from frtb_engine.notebook_tools import INR_CRORE, configure_notebooks, crore_table, draw_flow, heatmap

configure_notebooks()
ROOT = Path.cwd()
if not (ROOT / 'outputs').exists():
    ROOT = ROOT.parent
RUN_ID = (ROOT / 'outputs/latest_ima_run.txt').read_text(encoding='utf-8').strip()
RUN = ROOT / 'outputs' / RUN_ID
MANIFEST = json.loads((RUN / 'run_manifest.json').read_text(encoding='utf-8'))
STAGES = {row['stage']: ROOT / row['path'] for row in MANIFEST['artifacts']}
SUMMARY = json.loads((RUN / '27_combined_capital_summary.json').read_text(encoding='utf-8'))

def stage(name):
    return pd.read_csv(STAGES[name])

def money(value):
    return f"INR {float(value) / INR_CRORE:,.2f} crore"

print(f'IMA calculation run used: {RUN_ID}')
print('Reporting currency: INR | Synthetic and regulatory inputs remain separately labelled')"""


VISUAL_EXPLANATIONS = {
    30: {
        0: "The flow diagram shows the order of the complete calculation. SA and IMA begin with the same trades and risk factors. The IMA branch then separates modellable factors, non-modellable factors and default risk before desk testing decides whether IMA or SA fallback is used.",
        1: "The bars compare the full-book SA benchmark with the amounts used to assemble the combined result. Eligible-desk IMA, any amber-desk surcharge and SA fallback are additive components. The final-capital bar is their total, so neither the SA benchmark nor the final-capital bar should be added to the three component bars.",
    },
    31: {1: "The first chart counts distinct IMA factors in each broad risk class and therefore shows where the model has the greatest factor granularity. The heatmap then shows which desks are exposed to those classes. A darker cell means that a desk is connected to more distinct factors in that risk class; it does not indicate a larger monetary sensitivity."},
    32: {1: "The first chart counts factors classified as Modellable Risk Factors (MRFs) and Non-Modellable Risk Factors (NMRFs) after RFET. The second chart shows the actual synthetic qualifying-observation dates for the sparsest and most frequently observed factors. Dense, well-spread dates support modellability; sparse dates explain why a factor can fail RFET."},
    33: {1: "The bar chart is a distribution of factor assignments: it counts how many factors have been assigned 10, 20, 40, 60 or 120 days. It is not the nested Expected Shortfall calculation. The heatmap uses the same full factor inventory and shows which risk classes create each horizon count. The nesting of these horizon groups is calculated in notebook 35."},
    34: {1: "The line chart indexes four representative factor levels to 100 on the first date, making changes in differently scaled markets comparable. Diverging paths show how rates, equity, FX and commodity conditions evolve through the synthetic regimes. The correlation heatmap uses daily changes, not levels: positive cells mean two factors usually move in the same direction on the same date, while negative cells mean they tend to move in opposite directions."},
    35: {1: "The bars show Expected Shortfall calculated from nested factor subsets. The 10-day bar contains all modellable factors; each longer threshold retains only factors whose assigned horizon is at least that threshold. These bars are intermediate subset ES values, not separate capital charges to be added directly. The flow diagram shows how rolling losses, tail averaging and square-root liquidity-horizon aggregation convert historical P&L into the final adjusted ES."},
    36: {1: "The first chart compares the four quantities used in stressed scaling: full-current ES, reduced-current ES, reduced-stress ES and the resulting scaled measure. The second chart evaluates every rolling 12-month candidate period; its highest point identifies the stress window used for capital rather than a manually selected episode."},
    37: {1: "The bars show the two inputs to the 50/50 IMCC formula and its output. The constrained risk-class sum is larger because it restricts diversification between broad risk classes. The flow diagram makes the weighting explicit: half of the all-risk result and half of the constrained class sum form final IMCC."},
    38: {1: "The horizontal bars rank NMRFs by their selected stress-scenario loss, revealing which failed factors drive SES. The flow diagram shows why these losses remain outside modellable-factor ES: RFET failure leads to a horizon-adjusted stress loss and then the prescribed regulatory aggregation."},
    39: {1: "The first chart is the simulated one-year portfolio default-loss distribution. Most scenarios have modest loss, while the dashed line marks the 99.9th-percentile tail loss used for current IMA DRC. The second chart separates issuer default likelihood from signed Jump-to-Default exposure. Positive values create loss on default; negative values represent short-credit positions that can offset loss in joint scenarios."},
    40: {1: "The first chart counts each documented type of synthetic position change across the 501 position dates. It explains how often resizing, hedge adjustment and the final current-book anchor occur. The second chart follows five selected trades through time: a multiplier of 1 is the current size, values above 1 are larger historical positions and values below 1 are reductions."},
    41: {1: "The first chart overlays Credit desk HPL and RTPL for the 250-day PLA window. Close movement indicates that the risk model explains the full-pricing P&L, while persistent gaps weaken attribution. The scatter plot applies the same comparison to every tested desk: points close to the 45-degree relationship indicate close HPL–RTPL agreement, while wider dispersion is consistent with amber or red classification."},
    42: {1: "The first chart compares each Rates desk next-day loss with the 99% VaR forecast made one day earlier. Red points are dates on which realised HPL loss exceeded the forecast threshold. The second chart shows both HPL and APL exceptions at 97.5% and 99% for every desk over 250 observations."},
    43: {1: "The first chart counts the final desk treatments: green IMA, amber IMA and SA fallback. The second chart plots each tested desk using its two PLA statistics. Moving right means stronger Spearman association; moving upward means greater KS distribution separation. The dashed lines show the green-zone boundaries, so the preferred region is to the right of the vertical line and below the horizontal line."},
    44: {1: "The two line panels show the retained 60-day histories used for the current-versus-average comparison. IMCC is recalculated from each dated 250-day window using the current calibrated stress period. SES stays level because the current NMRF stress scenarios and current constant-tenor positions are held fixed across this averaging view. The larger of current non-DRC capital and the multiplier-adjusted average becomes the charge."},
    45: {1: "The first chart shows the three amounts added to obtain final market-risk capital: eligible-desk IMA, the amber surcharge and SA fallback. The second visual uses separate panels because capital and RWA have different scales. The left panel compares the full-book SA benchmark with combined SA–IMA capital; the right panel shows Market RWA, which equals combined capital multiplied by 12.5."},
    46: {1: "The lineage diagram reads from the reported capital amount back through desk treatment, capital measure, period, scenario, factor and trade exposure. The horizontal bar chart shows the final capital treatment by desk. It makes clear which desks dominate the reported total after each desk has been assigned either IMA or SA fallback."},
}


def code_for(number: int) -> list[str]:
    if number == 30:
        return [
            """draw_flow(['Shared trading book','Pricing and factors','SA: SBM + DRC + RRAO','IMA: RFET','MRF → ES → IMCC','NMRF → SES','IMA DRC','PLA + backtesting','Desk eligibility','SA fallback','Final capital','Market RWA'], 'One trading book, two FRTB approaches', wrap_after=4)""",
            """capital=pd.Series({'Full-book SA benchmark':SUMMARY['full_book_sa_capital_inr'],'Eligible-desk IMA before surcharge':SUMMARY['ima_eligible_capital_before_surcharge_inr'],'PLA amber surcharge':SUMMARY['pla_amber_surcharge_inr'],'SA fallback':SUMMARY['sa_fallback_capital_inr'],'Final market-risk capital':SUMMARY['final_frtb_market_risk_capital_inr']})
display((capital/INR_CRORE).rename('INR crore').to_frame())
ax=(capital/INR_CRORE).plot(kind='bar',color=['#6B7280','#2563EB','#F59E0B','#DC2626','#0F766E'])
ax.set_ylabel('INR crore'); ax.set_title('Capital components, combined result and full-book SA benchmark',loc='left',weight='bold'); ax.tick_params(axis='x',rotation=25); plt.tight_layout(); plt.show()
print(f"Final capital {money(SUMMARY['final_frtb_market_risk_capital_inr'])} × 12.5 = Market RWA {money(SUMMARY['market_rwa_inr'])}")""",
        ]
    if number == 31:
        return [
            """inventory=stage('01_ima_factor_inventory'); exposures=stage('05_factor_exposures')
inventory_sample=inventory[['risk_factor_id','broad_risk_class','desks','trade_count','signed_sensitivity_inr','liquidity_horizon_days','input_data_status']].head(20)
print(f'Displayed sample: first 20 of {len(inventory):,} factors in the full inventory.')
display(inventory_sample)
example=exposures[exposures.trade_id=='R12'][['trade_id','desk','risk_factor_id','broad_risk_class','ima_risk_measure','raw_sensitivity']]
print('The cross-currency basis swap R12 produces these IMA factor exposures:'); display(crore_table(example,['raw_sensitivity']))""",
            """counts=inventory.groupby('broad_risk_class').risk_factor_id.nunique().sort_values()
ax=counts.plot(kind='barh',color='#2563EB'); ax.set_xlabel('Distinct risk factors'); ax.set_title('IMA factor coverage by broad risk class',loc='left',weight='bold'); plt.tight_layout(); plt.show()
desk_factor=exposures.groupby(['desk','broad_risk_class']).risk_factor_id.nunique().unstack(fill_value=0)
heatmap(desk_factor,'Distinct factors linking each desk to each risk class',value_format='.0f')""",
        ]
    if number == 32:
        return [
            """rfet=stage('03_rfet_results'); obs=stage('02_synthetic_rpo_observations')
display(rfet[['risk_factor_id','qualifying_observation_count','minimum_observations_in_any_90_days','rfet_route','modellability_status','rfet_reason']])
worked=rfet.iloc[0]
print(f"Worked factor {worked.risk_factor_id}: {worked.qualifying_observation_count} qualifying dates and minimum {worked.minimum_observations_in_any_90_days} in any 90-day window → {worked.modellability_status}")""",
            """counts=rfet.modellability_status.value_counts(); ax=counts.plot(kind='bar',color=['#0F766E','#DC2626']); ax.set_ylabel('Risk-factor count'); ax.set_title('RFET separates MRFs from NMRFs',loc='left',weight='bold'); ax.tick_params(axis='x',rotation=0); plt.tight_layout(); plt.show()
examples=rfet.sort_values('qualifying_observation_count').iloc[[0,-1]].risk_factor_id.tolist(); sample=obs[obs.risk_factor_id.isin(examples)].copy(); sample['observation_date']=pd.to_datetime(sample.observation_date)
fig,ax=plt.subplots();
for y,(factor,g) in enumerate(sample.groupby('risk_factor_id')): ax.scatter(g.observation_date,[y]*len(g),s=18,label=factor)
ax.set_yticks([]); ax.set_title('Synthetic RFET evidence dates: sparse versus frequent',loc='left',weight='bold'); ax.legend(); plt.tight_layout(); plt.show()""",
        ]
    if number == 33:
        return [
            """inventory=stage('01_ima_factor_inventory')
view=inventory[['risk_factor_id','broad_risk_class','liquidity_category','liquidity_horizon_days','factor_type']]
displayed_sample=view.sort_values(['liquidity_horizon_days','broad_risk_class']).head(30)
print(f'Displayed sample: first 30 of {len(view):,} factors after sorting by liquidity horizon and risk class.')
print('The sample does not contain every horizon. The charts below use the complete factor inventory, including 60-day and 120-day factors.')
display(displayed_sample)
example=view[view.risk_factor_id.str.contains('OIS_VOL')].iloc[0]
print(f"{example.risk_factor_id} is interest-rate volatility, so its factor horizon is {example.liquidity_horizon_days} days even though its option tenor is separate.")""",
            """distribution=inventory.liquidity_horizon_days.value_counts().sort_index(); ax=distribution.plot(kind='bar',color='#2563EB'); ax.set_xlabel('Assigned liquidity horizon (days)'); ax.set_ylabel('Number of risk factors'); ax.set_title('Number of risk factors assigned to each liquidity horizon',loc='left',weight='bold'); ax.tick_params(axis='x',rotation=0); plt.tight_layout(); plt.show()
cross=inventory.groupby(['broad_risk_class','liquidity_horizon_days']).size().unstack(fill_value=0); heatmap(cross,'Factor counts by risk class and liquidity horizon',value_format='.0f')""",
        ]
    if number == 34:
        return [
            """history=stage('04_synthetic_factor_history'); pnl=stage('06_daily_factor_pnl'); history['date']=pd.to_datetime(history.date)
print(f"History covers {history.date.min().date()} to {history.date.max().date()} and is labelled {history.data_status.iloc[0]}.")
history_sample=history[['date','risk_factor_id','daily_change','level','market_regime','data_status']].head(5)
print(f'Displayed sample: first 5 of {len(history):,} factor-date observations.')
display(history_sample)
example=pnl.iloc[0]; print(f"Worked row: sensitivity × factor change plus nonlinear effect = {money(example.factor_pnl_inr)}")""",
            """selected=history[history.risk_factor_id.isin(['USDINR','NIFTY50','INR_OIS_5.0Y','BRENT_0.25Y_GLOBAL'])].pivot(index='date',columns='risk_factor_id',values='level'); normalized=selected/selected.iloc[0]*100
ax=normalized.plot(); ax.set_ylabel('Indexed level (start = 100)'); ax.set_title('Indexed paths of four representative synthetic risk factors',loc='left',weight='bold'); plt.tight_layout(); plt.show()
changes=history[history.risk_factor_id.isin(selected.columns)].pivot(index='date',columns='risk_factor_id',values='daily_change').corr(); heatmap(changes,'Same-date factor-change correlation',value_format='.2f')""",
        ]
    if number == 35:
        return [
            """components=stage('10_liquidity_horizon_es_components'); rowset=components[(components.scope=='ALL')&(components.period=='CURRENT')&(components.factor_set=='FULL')].copy()
shown=rowset.copy(); shown['subset_es_inr_crore']=shown.subset_es_inr/INR_CRORE; shown['squared_contribution_inr_crore_squared']=shown.squared_contribution/(INR_CRORE**2)
display(shown[['liquidity_horizon_days','subset_es_inr_crore','scaling_increment','squared_contribution_inr_crore_squared']])
base=rowset.iloc[0]; print(f"10-day portfolio ES = {money(base.subset_es_inr)}. Longer-horizon squared contributions are then added before taking the square root.")""",
            """ax=(rowset.set_index('liquidity_horizon_days').subset_es_inr/INR_CRORE).plot(kind='bar',color='#2563EB'); ax.set_xlabel('Nested threshold (days)'); ax.set_ylabel('Subset ES (INR crore)'); ax.set_title('Expected Shortfall for each nested factor set',loc='left',weight='bold'); ax.tick_params(axis='x',rotation=0); plt.tight_layout(); plt.show()
draw_flow(['Joint daily P&L','Rolling 10-day P&L','97.5% loss threshold','Average tail loss','Nested LH subsets','Square-root aggregation'],'From historical P&L to liquidity-horizon ES',wrap_after=6)""",
        ]
    if number == 36:
        return [
            """scaled=stage('11_scaled_es_and_imcc'); scan=stage('08_stress_window_scan'); selection=stage('07_reduced_factor_selection')
display(crore_table(scaled,['full_current_es_inr','reduced_current_es_inr','reduced_stress_es_inr','scaled_es_capital_inr']))
allrow=scaled[scaled.scope=='ALL'].iloc[0]
print(f"Reduced-set coverage = {allrow.reduced_set_coverage:.1%}; scaling ratio = max({allrow.full_current_es_inr/allrow.reduced_current_es_inr:.4f}, 1) = {allrow.stress_scaling_ratio:.4f}.")""",
            """bridge=pd.Series({'Full current':allrow.full_current_es_inr,'Reduced current':allrow.reduced_current_es_inr,'Reduced stress':allrow.reduced_stress_es_inr,'Scaled stress measure':allrow.scaled_es_capital_inr})/INR_CRORE
ax=bridge.plot(kind='bar',color=['#6B7280','#2563EB','#DC2626','#0F766E']); ax.set_ylabel('INR crore'); ax.set_title('Full, reduced, current and stress ES bridge',loc='left',weight='bold'); ax.tick_params(axis='x',rotation=20); plt.tight_layout(); plt.show()
scan['window_start']=pd.to_datetime(scan.window_start); ax=(scan.sort_values('window_start').set_index('window_start').reduced_lh_adjusted_es_inr/INR_CRORE).plot(color='#DC2626'); ax.set_ylabel('Reduced ES (INR crore)'); ax.set_title('Rolling 12-month stress-window scan',loc='left',weight='bold'); plt.tight_layout(); plt.show()""",
        ]
    if number == 37:
        return [
            """scaled=stage('11_scaled_es_and_imcc'); unconstrained=scaled.loc[scaled.scope=='ALL','scaled_es_capital_inr'].iloc[0]; constrained=scaled.loc[scaled.scope!='ALL','scaled_es_capital_inr'].sum(); imcc=0.5*unconstrained+0.5*constrained
display(crore_table(scaled[['scope','scaled_es_capital_inr']],['scaled_es_capital_inr']))
print(f"IMCC = 50% × {money(unconstrained)} + 50% × {money(constrained)} = {money(imcc)}")""",
            """parts=pd.Series({'Unconstrained all-risk ES':unconstrained,'Constrained risk-class sum':constrained,'Final IMCC':imcc})/INR_CRORE; ax=parts.plot(kind='bar',color=['#2563EB','#F59E0B','#0F766E']); ax.set_ylabel('INR crore'); ax.set_title('Inputs and output of the 50/50 IMCC aggregation',loc='left',weight='bold'); ax.tick_params(axis='x',rotation=18); plt.tight_layout(); plt.show()
draw_flow(['Scaled all-risk ES','50% unconstrained','Five scaled class ES values','50% constrained sum','IMCC'],'Constrained and unconstrained ES join into IMCC',wrap_after=5)""",
        ]
    if number == 38:
        return [
            """detail=stage('12_nmrf_ses_detail'); summary=stage('13_nmrf_ses_summary')
display(crore_table(detail,['empirical_stress_loss_inr','parametric_stress_loss_inr','stress_scenario_loss_inr']))
display(crore_table(summary,['idiosyncratic_credit_inr','idiosyncratic_equity_inr','other_nmrf_inr','ses_inr']))
worked=detail.iloc[0]; print(f"{worked.risk_factor_id}: max(empirical {money(worked.empirical_stress_loss_inr)}, parametric {money(worked.parametric_stress_loss_inr)}) = {money(worked.stress_scenario_loss_inr)}")""",
            """ax=(detail.set_index('risk_factor_id').stress_scenario_loss_inr/INR_CRORE).sort_values().plot(kind='barh',color='#DC2626'); ax.set_xlabel('Stress loss (INR crore)'); ax.set_title('NMRF stress loss by factor',loc='left',weight='bold'); plt.tight_layout(); plt.show()
draw_flow(['RFET failure','NMRF','max(LH, 20 days)','Empirical and parametric stress','Factor loss','Regulatory aggregation','SES'],'How non-modellable factors produce SES',wrap_after=7)""",
        ]
    if number == 39:
        return [
            """issuers=stage('14_ima_drc_issuer_inputs'); distribution=stage('15_ima_drc_loss_distribution'); trace=stage('16_ima_drc_tail_trace'); weekly=stage('17_ima_drc_weekly_history')
display(crore_table(issuers[['obligor','rating','sector','economy','pd','default_threshold','exposure_jtd_inr','systematic_group']],['exposure_jtd_inr']))
current=SUMMARY['ima_drc_current_inr']; average=SUMMARY['ima_drc_average_12_week_inr']; print(f"IMA DRC capital = max(current {money(current)}, 12-week average {money(average)}) = {money(SUMMARY['ima_drc_capital_inr'])}")
print(f'Displayed sample: first 10 of {len(trace):,} retained tail simulations.')
display(trace.head(10))""",
            """ax=distribution.plot(x='loss_band_inr',y='simulation_count',color='#DC2626',legend=False); ax.axvline(current,color='black',linestyle='--',label='99.9% VaR'); ax.set_xlabel('One-year default loss (INR)'); ax.set_ylabel('Simulation count'); ax.ticklabel_format(axis='x',style='plain'); ax.set_title('Correlated one-year default-loss distribution',loc='left',weight='bold'); ax.legend(); plt.tight_layout(); plt.show()
fig,ax=plt.subplots(); ax.scatter(issuers.pd*100,issuers.exposure_jtd_inr/INR_CRORE,s=55,color='#2563EB');
for _,r in issuers.iterrows(): ax.annotate(r.obligor,(r.pd*100,r.exposure_jtd_inr/INR_CRORE),fontsize=7)
ax.axhline(0,color='#6B7280',linewidth=.8); ax.set_xlabel('PD (%)'); ax.set_ylabel('Signed JTD exposure (INR crore)'); ax.set_title('Issuer PD and signed JTD exposure entering IMA DRC',loc='left',weight='bold'); plt.tight_layout(); plt.show()""",
        ]
    if number == 40:
        return [
            """snap=stage('18_portfolio_snapshots'); snap['date']=pd.to_datetime(snap.date)
print(f"{snap.trade_id.nunique()} shared trades across {snap.date.nunique()} business dates produce {len(snap):,} stored position rows.")
changed=snap[snap.position_event!='UNCHANGED']
print(f'Displayed sample: first 20 of {len(changed):,} rows containing a documented position event.')
display(changed.head(20))
example=snap[snap.trade_id=='R09'].sort_values('date'); print('The position multiplier changes the size of the same underlying trade; it does not create a different portfolio universe.')""",
            """events=snap[snap.position_event!='UNCHANGED'].position_event.value_counts(); ax=events.plot(kind='bar',color='#2563EB'); ax.set_ylabel('Snapshot rows'); ax.set_title('Documented position changes in the synthetic history',loc='left',weight='bold'); ax.tick_params(axis='x',rotation=20); plt.tight_layout(); plt.show()
fig,ax=plt.subplots();
for trade in ['R09','C07','E03','F03','M06']:
 g=snap[snap.trade_id==trade]; ax.plot(g.date,g.position_multiplier,label=trade)
ax.set_ylabel('Position multiplier'); ax.set_title('Reproducible position evolution for selected derivatives',loc='left',weight='bold'); ax.legend(ncol=5); plt.tight_layout(); plt.show()""",
        ]
    if number == 41:
        return [
            """daily=stage('19_daily_hpl_rtpl_apl'); pla=stage('20_pla_results'); daily['date']=pd.to_datetime(daily.date)
display(pla)
credit=pla[pla.desk=='Credit'].iloc[0]; print(f"Credit desk: Spearman {credit.spearman_correlation:.3f}, KS {credit.ks_statistic:.3f} → {credit.pla_zone}.")
print('Displayed sample: final 10 daily Credit desk observations from the 250-day PLA window.')
display(crore_table(daily[daily.desk=='Credit'][['date','hpl_inr','rtpl_inr','apl_inr']].tail(10),['hpl_inr','rtpl_inr','apl_inr']))""",
            """sample=daily[daily.desk=='Credit'].tail(250); ax=sample.plot(x='date',y=['hpl_inr','rtpl_inr']); ax.set_ylabel('Daily P&L (INR)'); ax.ticklabel_format(axis='y',style='plain'); ax.set_title('Credit desk HPL and RTPL over the PLA window',loc='left',weight='bold'); plt.tight_layout(); plt.show()
fig,ax=plt.subplots();
colors={'GREEN':'#0F766E','AMBER':'#F59E0B','RED':'#DC2626'}
for desk,g in daily.groupby('desk'):
 s=g.tail(250); zone=pla.loc[pla.desk==desk,'pla_zone'].iloc[0]; ax.scatter(s.hpl_inr/INR_CRORE,s.rtpl_inr/INR_CRORE,s=8,alpha=.45,label=f'{desk}: {zone}',color=colors[zone])
low=min(ax.get_xlim()[0],ax.get_ylim()[0]); high=max(ax.get_xlim()[1],ax.get_ylim()[1]); ax.plot([low,high],[low,high],color='#6B7280',linestyle='--',linewidth=1,label='Exact HPL = RTPL agreement'); ax.set_xlim(low,high); ax.set_ylim(low,high)
ax.set_xlabel('HPL (INR crore)'); ax.set_ylabel('RTPL (INR crore)'); ax.set_title('PLA compares the same-day full and model P&L representations',loc='left',weight='bold'); ax.legend(fontsize=8); plt.tight_layout(); plt.show()""",
        ]
    if number == 42:
        return [
            """detail=stage('21_backtesting_detail'); summary=stage('22_backtesting_summary'); detail['outcome_date']=pd.to_datetime(detail.outcome_date)
display(summary)
rates=summary[summary.desk=='Rates'].iloc[0]; print(f"Rates desk HPL/APL exceptions: 99% = {int(rates.hpl_exceptions_99)}/{int(rates.apl_exceptions_99)}; 97.5% = {int(rates.hpl_exceptions_97_5)}/{int(rates.apl_exceptions_97_5)}; result = {rates.backtesting_result}.")""",
            """sample=detail[detail.desk=='Rates'].sort_values('outcome_date'); fig,ax=plt.subplots(); ax.plot(sample.outcome_date,-sample.next_day_hpl_inr/INR_CRORE,label='Next-day HPL loss'); ax.plot(sample.outcome_date,sample.var_99_inr/INR_CRORE,label='99% VaR forecast'); exc=sample[sample.hpl_exception_99]; ax.scatter(exc.outcome_date,-exc.next_day_hpl_inr/INR_CRORE,color='#DC2626',label='99% exception'); ax.set_ylabel('INR crore'); ax.set_title('Rates desk: 99% VaR forecast at t versus HPL loss at t+1',loc='left',weight='bold'); ax.legend(); plt.tight_layout(); plt.show()
exceptions=summary.set_index('desk')[['hpl_exceptions_97_5','apl_exceptions_97_5','hpl_exceptions_99','apl_exceptions_99']]; ax=exceptions.plot(kind='bar'); ax.set_ylabel('Exceptions in 250 observations'); ax.set_title('HPL and APL exception counts at both VaR confidence levels',loc='left',weight='bold'); ax.tick_params(axis='x',rotation=20); plt.tight_layout(); plt.show()""",
        ]
    if number == 43:
        return [
            """elig=stage('23_desk_eligibility')
display(elig[['desk','pla_zone','backtesting_result','final_treatment','eligibility_reason']])
for _,r in elig.iterrows(): print(f"{r.desk}: {r.final_treatment} — {r.eligibility_reason}")""",
            """order=['IMA_GREEN','IMA_AMBER','SA_FALLBACK']; counts=elig.final_treatment.value_counts().reindex(order,fill_value=0); ax=counts.plot(kind='bar',color=['#0F766E','#F59E0B','#DC2626']); ax.set_ylabel('Number of desks'); ax.set_title('Number of desks receiving each final model treatment',loc='left',weight='bold'); ax.tick_params(axis='x',rotation=0); plt.tight_layout(); plt.show()
metrics=elig[elig.pla_zone!='NOT_APPLICABLE'].copy(); colors={'GREEN':'#0F766E','AMBER':'#F59E0B','RED':'#DC2626'}; fig,ax=plt.subplots();
for _,r in metrics.iterrows(): ax.scatter(r.spearman_correlation,r.ks_statistic,s=70,color=colors[r.pla_zone]); ax.annotate(r.desk,(r.spearman_correlation,r.ks_statistic),xytext=(4,4),textcoords='offset points',fontsize=8)
ax.axvline(.8,color='#0F766E',linestyle='--',label='Spearman green boundary = 0.80'); ax.axhline(.09,color='#DC2626',linestyle=':',label='KS green boundary = 0.09'); ax.set_xlabel('Spearman correlation — higher is better'); ax.set_ylabel('KS statistic — lower is better'); ax.set_title('Desk PLA metrics relative to green-zone boundaries',loc='left',weight='bold'); ax.legend(fontsize=8); plt.tight_layout(); plt.show()""",
        ]
    if number == 44:
        return [
            """history=stage('24_ima_capital_history'); bank=stage('26_bankwide_backtesting'); history['date']=pd.to_datetime(history.date)
current=SUMMARY['imcc_current_inr']+SUMMARY['ses_current_inr']; average=SUMMARY['backtesting_multiplier']*SUMMARY['imcc_average_60_day_inr']+SUMMARY['ses_average_60_day_inr']
print(f"Current IMCC + SES = {money(current)}")
print(f"Multiplier-adjusted average IMCC + average SES = {money(average)}")
print(f"Selected non-DRC capital = {money(SUMMARY['ima_non_drc_capital_inr'])}")
display(bank)""",
            """fig,axes=plt.subplots(2,1,sharex=True,figsize=(11,6)); axes[0].plot(history.date,history.imcc_inr/INR_CRORE,color='#2563EB'); axes[0].set_ylabel('INR crore'); axes[0].set_title('Reconstructed IMCC: current positions and stress calibration',loc='left',weight='bold'); axes[1].plot(history.date,history.ses_inr/INR_CRORE,color='#DC2626'); axes[1].set_ylabel('INR crore'); axes[1].set_title('Reconstructed SES: current positions and stress calibration',loc='left',weight='bold'); plt.tight_layout(); plt.show()
parts=pd.Series({'Current IMCC + SES':current,'Multiplier-adjusted average':average,'IMA DRC capital':SUMMARY['ima_drc_capital_inr'],'PLA amber surcharge':SUMMARY['pla_amber_surcharge_inr']})/INR_CRORE; ax=parts.plot(kind='bar',color=['#2563EB','#F59E0B','#7C3AED','#DC2626']); ax.set_ylabel('INR crore'); ax.set_title('Eligible-desk IMA capital components',loc='left',weight='bold'); ax.tick_params(axis='x',rotation=20); plt.tight_layout(); plt.show()""",
        ]
    if number == 45:
        return [
            """desk=stage('25_desk_capital_summary')
capital_columns=['sa_capital_inr','ima_component_inr','amber_surcharge_inr','sa_fallback_component_inr','final_capital_treatment_inr']
display(crore_table(desk[['desk','final_treatment',*capital_columns]],capital_columns))
print(f"Eligible IMA before surcharge {money(SUMMARY['ima_eligible_capital_before_surcharge_inr'])} + amber surcharge {money(SUMMARY['pla_amber_surcharge_inr'])} + SA fallback {money(SUMMARY['sa_fallback_capital_inr'])} = {money(SUMMARY['final_frtb_market_risk_capital_inr'])}")
print(f"Market RWA = 12.5 × capital = {money(SUMMARY['market_rwa_inr'])}")""",
            """parts=pd.Series({'Eligible IMA':SUMMARY['ima_eligible_capital_before_surcharge_inr'],'Amber surcharge':SUMMARY['pla_amber_surcharge_inr'],'SA fallback':SUMMARY['sa_fallback_capital_inr']})/INR_CRORE; ax=parts.plot(kind='bar',color=['#2563EB','#F59E0B','#DC2626']); ax.set_ylabel('INR crore'); ax.set_title('Components added to obtain final market-risk capital',loc='left',weight='bold'); ax.tick_params(axis='x',rotation=10); plt.tight_layout(); plt.show()
capital_comparison=pd.Series({'Full-book SA benchmark':SUMMARY['full_book_sa_capital_inr'],'Combined SA + IMA capital':SUMMARY['final_frtb_market_risk_capital_inr']})/INR_CRORE; fig,axes=plt.subplots(1,2,figsize=(12,5)); capital_comparison.plot(kind='bar',ax=axes[0],color=['#6B7280','#0F766E']); axes[0].set_ylabel('INR crore'); axes[0].set_title('Capital benchmark versus combined capital',loc='left',weight='bold'); axes[0].tick_params(axis='x',rotation=18); pd.Series({'Market RWA':SUMMARY['market_rwa_inr']/INR_CRORE}).plot(kind='bar',ax=axes[1],color='#7C3AED'); axes[1].set_ylabel('INR crore'); axes[1].set_title('Market RWA after the 12.5 multiplier',loc='left',weight='bold'); axes[1].tick_params(axis='x',rotation=0); plt.tight_layout(); plt.show()""",
        ]
    return [
        """desk=stage('25_desk_capital_summary'); manifest=pd.DataFrame(MANIFEST['artifacts'])
capital_columns=['sa_capital_inr','ima_component_inr','amber_surcharge_inr','sa_fallback_component_inr','final_capital_treatment_inr']
display(crore_table(desk[['desk','final_treatment',*capital_columns]],capital_columns))
display(manifest[['stage','rows','path']])
print(f"The run retains {len(manifest)} calculation artifacts. Every capital amount can be followed to its dated scenarios, factors and trades.")""",
        """draw_flow(['Final capital','Desk treatment','IMCC / SES / DRC / SA','Current or stress period','Historical scenario','Risk factor','Trade exposure'],'Calculation lineage retained by the reporting layer',wrap_after=7)
ax=(desk.set_index('desk').final_capital_treatment_inr/INR_CRORE).sort_values().plot(kind='barh',color='#2563EB'); ax.set_xlabel('Final treatment capital (INR crore)'); ax.set_title('Desk-level capital view used by reporting',loc='left',weight='bold'); plt.tight_layout(); plt.show()""",
    ]


def build() -> None:
    NOTEBOOKS.mkdir(parents=True, exist_ok=True)
    for number, topic in enumerate(TOPICS, start=30):
        notebook = nbf.v4.new_notebook()
        notebook.metadata.kernelspec = {"display_name": "FRTB SA Local", "language": "python", "name": "frtb-sa-local"}
        notebook.metadata.language_info = {"name": "python", "version": "3.12"}
        opening = f"# {number} — {topic.title}\n\n{topic.purpose}"
        explanation = (
            f"{topic.explanation}\n\n"
            f"This step uses: {topic.inputs}\n\n"
            f"It produces: {topic.output}\n\n"
            f"> {topic.norm}\n\n{topic.formula}\n\n"
            "Synthetic inputs are labelled directly in the displayed data. Basel regulatory parameters are loaded separately from versioned configuration."
        )
        notebook.cells = [nbf.v4.new_markdown_cell(opening), nbf.v4.new_markdown_cell(explanation), nbf.v4.new_code_cell(SETUP)]
        for cell_index, code in enumerate(code_for(number)):
            notebook.cells.append(nbf.v4.new_code_cell(code))
            visual_explanation = VISUAL_EXPLANATIONS.get(number, {}).get(cell_index)
            if visual_explanation:
                notebook.cells.append(nbf.v4.new_markdown_cell(visual_explanation))
        nbf.write(notebook, NOTEBOOKS / f"{number:02d}_{topic.slug}.ipynb")
        print(f"Built {number:02d}_{topic.slug}.ipynb")


if __name__ == "__main__":
    build()
