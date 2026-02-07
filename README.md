# Portfolio Stress Testing Project

## Overview
This project implements a **historical, scenario-based stress testing framework** to evaluate how a multi-asset portfolio would have performed across major financial crises and macroeconomic shock events. The analysis focuses on portfolio-level returns, asset-level contributions, and identification of key loss drivers under different market regimes.

The framework is designed to be **transparent, reproducible, and analytically defensible**, with explicit handling of historical data availability constraints to avoid look-ahead bias or data fabrication.

---

## Files
- code+result.ipynb: main notebook: data loading, stress testing, analysis
- portfolio.csv: portfolio weights
- scenarios.csv: stress windows
- output_prices: asset prices from IBKR

## Data Inputs

### Portfolio
- **portfolio.csv**  
  Contains portfolio asset weights (e.g. SPY, TLT, GLD, EURUSD).

### Stress Scenarios
- **scenarios.csv**  
  Defines historical stress scenarios with:
  - `scenario`: scenario identifier (e.g. afc, dot_com, gfc)
  - `start_date`
  - `end_date`

### Market Data
- Historical price data is sourced from **IBKR** and **Yahoo Finance (yfinance)**.
- Assets without valid historical data for a given scenario are intentionally excluded (recorded as `NaN`) to ensure methodological integrity.

---

## Stress Scenarios Covered

- **afc** – Asian Financial Crisis (1997–1998)
- **russian_default_ltcm** – Russia’s 1998 default and LTCM collapse
- **dot_com** – Burst of the technology bubble (2000–2002)
- **gfc** – Global Financial Crisis (2007–2009)
- **flash_crash** – May 2010 liquidity-driven market crash
- **fukushima_meltdown** – 2011 Japan earthquake and nuclear disaster
- **sp_downgrade** – 2011 US sovereign credit downgrade
- **euro_debt_crisis** – European sovereign debt stress
- **taper_tantrum** – 2013 Fed tapering shock
- **a50_turbulence** – China equity market turbulence (2015–2016)
- **brexit** – UK referendum to leave the EU
- **us_presidential_election** – 2016 US election volatility
- **volmageddon** – February 2018 volatility spike
- **covid19** – Global pandemic shock
- **global_inflation** – Post-pandemic inflation and rate hikes
- **fitch_downgrade** – 2023 US credit downgrade
- **carry_trade_unwind** – Global FX carry trade unwinding
- **trump_tariffs** – US–China trade tensions
- **gold_silver_bust** – Precious metals correction

---

## Methodology

1. **Scenario Date Alignment**  
   Scenario start and end dates are aligned to actual trading days using the most recent available price on or before each date, ensuring no look-ahead bias.

2. **Asset-Level Returns**  
   Asset returns are computed over each scenario window using adjusted closing prices.

3. **Portfolio Contributions**  
   Portfolio contribution is calculated as: contribution = weight × asset_return

4. **Loss Driver Analysis**  
For each scenario, the largest negative contributors are identified to determine the primary sources of portfolio losses.

5. **Data Availability Handling**  
For early historical scenarios (e.g. AFC, Russian Default & LTCM, Dot-com), only assets with available data are included. As a result, these scenarios may be driven solely by equity exposure (e.g. SPY), leading to more pronounced portfolio movements.

---

## Key Outputs

- Scenario-level portfolio returns
- Asset-level returns and contributions
- Ranking of stress scenarios by severity
- Identification of main loss drivers per scenario
- Comparative analysis of equity-driven vs macro-driven stress regimes

---

## How to Run

### Using pip
```bash
pip install -r requirements.txt
```

## Notes & Limitations

Results for early-period scenarios may appear more extreme due to limited asset availability and reduced diversification.
This project is intended for analytical and educational purposes only and does not constitute investment advice.
