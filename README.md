# Stress Testing a Multi-Asset Portfolio Using IBKR Positions

## Overview
This project implements a **historical scenario stress-testing framework** for a multi-asset portfolio.  
Unlike static backtests that rely on predefined weights, the portfolio composition and weights are **pulled dynamically from Interactive Brokers (IBKR)**, ensuring that stress results reflect **actual live positions**.

The framework evaluates how the portfolio would have performed during major historical market stress events (e.g. COVID-19, Dot-com crash, Global Financial Crisis) by decomposing **asset-level returns** and **portfolio-level contributions**.

---

## Key Features
- **Dynamic portfolio construction from IBKR**
  - Pulls open positions directly from IBKR (stocks, ETFs, futures)
  - Computes **gross portfolio weights** from live position values
  - No reliance on static `portfolio.csv`

- **Robust historical price retrieval**
  - Pulls daily historical prices using:
    - IBKR (with chunking to avoid API limits)
    - Yahoo Finance (`yfinance`) as a fallback / alternative data source
  - Gracefully handles limited history and asset inception dates

- **Scenario-based stress testing**
  - Evaluates portfolio performance across predefined historical crises
  - Avoids look-ahead bias by using the nearest available trading date ≤ scenario bounds

- **Asset-level contribution analysis**
  - Separates pure asset returns from portfolio impact
  - Identifies which assets drive losses or gains in each scenario

---

## Project Structure
- code + results.ipynb # Main notebook: data pull, stress tests, results
- output_prices # Saved historical price series (CSV per asset)
- scenarios.csv # Stress scenario definitions (dates + labels)


> **Note:** `portfolio.csv` has been intentionally removed.  
> Portfolio weights are now derived entirely from IBKR positions.

---

## Methodology

### 1. Portfolio Construction
- Open positions are retrieved from IBKR using `ib_insync`
- Each position’s **signed market value** is computed:
position_value = quantity × price × multiplier
- **Gross weights** are calculated as:
weight = position_value / sum(|position_value|)
- Positions without valid prices are excluded from analysis

---

### 2. Historical Price Data
- Daily price history is pulled for each asset:
- Chunked requests (1 year per request) to avoid IBKR limits
- Missing or unavailable history (e.g. pre-IPO periods) is handled gracefully
- Assets are saved individually under `output_prices/`

---

### 3. Stress Scenarios
Each scenario specifies:
- A historical event (e.g. `covid19`, `dot_com`, `gfc`)
- A start and end date defining the stress window

Asset returns are computed as:
(Price at end of scenario / Price at start of scenario) − 1

The nearest trading day ≤ each date is used to avoid look-ahead bias.

---

### 4. Portfolio Impact
- **Asset return**: price movement over the scenario window
- **Contribution**:
contribution = weight × asset_return

- Portfolio-level stress return is the sum of contributions across assets

---

## Interpreting Results
- Negative portfolio returns indicate stress vulnerability
- Scenario severity is ranked by portfolio return
- Asset-level contributions identify **which exposures drive risk**
- In this portfolio, downside risk is largely driven by **equity beta**, particularly S&P 500 futures exposure

---

## Known Limitations
- Historical coverage varies by asset and exchange
- Some futures contracts only provide history for the active contract month
- Yahoo Finance coverage for non-US assets (e.g. SGX) may be incomplete

These limitations are handled explicitly and do not invalidate the stress-testing framework.

---

## Future Extensions
- Net-weight and capital-based stress testing
- Factor-level decomposition (equity beta, rates, FX)
- Automated scenario expansion and visualization dashboards
- Rolling stress tests using current portfolio snapshots

---

## Disclaimer
This project is for **educational and research purposes only** and does not constitute investment advice.
