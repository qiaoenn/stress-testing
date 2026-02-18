# Portfolio Tail-Risk Stress Test 

A Streamlit dashboard that pulls **live IBKR positions (local API)** and applies historical crisis shock scenarios to estimate portfolio performance under major tail events.

This tool answers:

> *"How would my current portfolio have performed during past crises?"*

---

## What This Does

1. Connects to **Interactive Brokers (TWS / IB Gateway)**
2. Pulls live portfolio positions
3. Computes derived portfolio weights (gross or net)
4. Applies historical crisis shock returns
5. Ranks worst-case portfolio outcomes
6. Provides asset-level contribution breakdown

---

## Stress Scenarios Included

Examples:

- Global Financial Crisis (GFC)
- Euro Debt Crisis
- Taper Tantrum
- Brexit
- Flash Crash
- Volmageddon
- COVID-19 crash
- Rating Downgrades
- Carry Trade Unwind

(Filtered to post-2007 by default.)

---

## Weight Modes

### **Gross Weight**

- weight_i = position_value_i / Σ |position_value|
- Measures total exposure regardless of direction.

### **Net Weight**

- weight_i = position_value_i / Σ position_value
- Reflects directional capital allocation.

---

## Important: IBKR API Requirement

This dashboard **cannot connect to IBKR from the public Streamlit link.**

IBKR API only allows connections from:
localhost (127.0.0.1)

Therefore:

To pull live IBKR positions, the app **must run locally** on the same machine as:

- TWS
- OR IB Gateway

---

# How To Run Locally

## 1. Clone Repository

```bash
git clone https://github.com/qiaoenn/stress-testing.git
cd stress-testing
```
## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## 3. Enable IBKR API

Open TWS or IB Gateway
Go to: Settings → API → Enable ActiveX and Socket Clients
Ensure:
Port = 7497 (Paper) or 7496 (Live) + Allow connections from localhost

## 4. Run the dashboard 

```bash
streamlit run app.py
```

## Limitations
- IBKR API requires local execution
- Market value fallback uses avgCost × quantity if marketValue unavailable
- Scenario set limited to available shock matrix
- No transaction cost modeling



