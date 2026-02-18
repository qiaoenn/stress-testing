import asyncio

# Fix for Python 3.12 + Streamlit + ib_insync
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import pandas as pd
import numpy as np
import streamlit as st
from ib_insync import IB

st.set_page_config(page_title="Tail Risk Stress Test", layout="wide")

# ---------- Load data ----------
@st.cache_data
def load_shock(path="data/processed/shock_matrix.parquet"):
    return pd.read_parquet(path)

@st.cache_data
def load_scenarios(path="data/processed/scenarios.parquet"):
    df = pd.read_parquet(path)
    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])
    return df

shock = load_shock()
scenarios = load_scenarios()


# ---------- Sidebar controls ----------
st.sidebar.header("Scenario Filter")
cutoff = pd.Timestamp(st.sidebar.date_input("Omit scenarios before", value=pd.Timestamp("2007-01-01")))

# keep only >= cutoff
keep_scenarios = scenarios.loc[scenarios["start_date"] >= cutoff, "scenario"].astype(str)
shock = shock.loc[shock.index.isin(set(keep_scenarios))].copy()

st.sidebar.header("IBKR Connection (Local)")
host = st.sidebar.text_input("Host", "127.0.0.1")
port = st.sidebar.number_input("Port", value=7497, step=1)
# Default clientId for PM use.
# Change only if another API connection is running and you see Error 326.
DEFAULT_CLIENT_ID = 1
client_id = DEFAULT_CLIENT_ID

weight_mode = st.sidebar.selectbox("Weight mode", ["gross", "net"], index=0)
normalize_weights = st.sidebar.checkbox("Normalize weights to sum to 1", value=True)

min_assets_required = st.sidebar.number_input(
    "Min assets required per scenario",
    min_value=1,
    max_value=200,
    value=2,
    step=1
)

# ---------- Helpers ----------
from ib_insync import IB
import streamlit as st

@st.cache_resource
def get_ib(host: str, port: int):
    """
    Connect to IBKR using a stable default clientId.
    If the clientId is already in use, fall back to another one automatically.
    """
    ib = IB()

    # Try a small list of clientIds to avoid collisions
    for cid in [1, 2, 3, 10, 11, 12, 13, 99]:
        try:
            ib.connect(host, int(port), clientId=int(cid), timeout=5)
            st.session_state["ib_client_id_used"] = cid
            return ib
        except Exception:
            pass

    raise RuntimeError("Unable to connect to IBKR. All fallback clientIds are in use or connection failed.")


def fetch_positions_with_weights(ib: IB, mode: str = "gross") -> pd.DataFrame:
    """
    Returns: DataFrame with symbol, position_value, weight
    Note: uses avgCost fallback if marketValue isn't available.
    """
    pos = ib.positions()
    rows = []

    for p in pos:
        c = p.contract
        symbol = str(c.symbol).upper().strip()

        # approximate position value
        # (some environments have p.marketValue; if not, fallback)
        mv = None
        if hasattr(p, "marketValue") and p.marketValue is not None:
            try:
                mv = float(p.marketValue)
            except Exception:
                mv = None
        if mv is None:
            mv = float(p.position) * float(p.avgCost)

        rows.append({
            "symbol": symbol,
            "sec_type": getattr(c, "secType", None),
            "exchange": getattr(c, "exchange", None),
            "quantity": float(p.position),
            "avg_cost": float(p.avgCost),
            "position_value": float(mv),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df[df["position_value"].notna() & (df["position_value"] != 0)].copy()

    if mode == "gross":
        denom = df["position_value"].abs().sum()
    else:  # net
        denom = df["position_value"].sum()

    if denom == 0:
        df["weight"] = np.nan
    else:
        df["weight"] = df["position_value"] / denom

    df = df.sort_values("weight", key=lambda s: s.abs(), ascending=False)
    return df

# ---------- UI ----------
st.title("Portfolio Tail-Risk Stress Test")
st.caption("Pulls local IBKR positions and applies historical crisis shocks (scenario × asset returns).")

# Load from IBKR
if st.button("Load portfolio from IBKR", key="load_ibkr_btn"):
    try:
        ib = get_ib(host, port)   # <-- note: no client_id argument anymore
        used = st.session_state.get("ib_client_id_used", "unknown")
        st.info(f"Connected to IBKR (clientId={used}). Fetching positions...")

        pf_full = fetch_positions_with_weights(ib, mode=weight_mode)
        st.session_state["pf_full"] = pf_full
        st.success("Loaded positions from IBKR.")
    except Exception as e:
        st.error(f"Failed to connect or fetch positions: {e}")

pf_full = st.session_state.get("pf_full")

if pf_full is None or pf_full.empty:
    st.info("Click **Load portfolio from IBKR** to pull positions.")
    st.stop()

st.subheader("IBKR Positions (derived weights)")

pf_show = pf_full.copy()

# format: weight as %
pf_show["weight (%)"] = (pf_show["weight"] * 100).round(2)
pf_show = pf_show.drop(columns=["weight"])

# format: 2dp
for col in ["avg_cost", "position_value"]:
    if col in pf_show.columns:
        pf_show[col] = pf_show[col].round(2)

pf_show = pf_show.reset_index(drop=True)
st.dataframe(pf_show, use_container_width=True)


portfolio = pf_full[["symbol", "weight"]].copy()
portfolio["symbol"] = portfolio["symbol"].astype(str).str.upper().str.strip()
portfolio["weight"] = pd.to_numeric(portfolio["weight"], errors="coerce")
portfolio = portfolio.dropna(subset=["symbol", "weight"])

# Align to shock matrix
available = set(shock.columns.astype(str))
portfolio["has_data"] = portfolio["symbol"].isin(available)

missing = portfolio.loc[~portfolio["has_data"], "symbol"].tolist()
if missing:
    st.warning(f"Missing shock data for: {missing}. They will be ignored.")

portfolio_ok = portfolio[portfolio["has_data"]].copy()

if portfolio_ok.empty:
    st.error("None of the portfolio symbols exist in the shock matrix.")
    st.stop()

# Normalize weights if asked
if normalize_weights:
    denom = portfolio_ok["weight"].abs().sum()
    if denom != 0:
        portfolio_ok["weight"] = portfolio_ok["weight"] / denom

w = portfolio_ok.set_index("symbol")["weight"]
shock_sub = shock[list(w.index)].copy()

# Coverage filter (drop scenarios with too few non-null assets)
coverage = shock_sub.notna().sum(axis=1)
shock_sub = shock_sub.loc[coverage >= int(min_assets_required)].copy()

if shock_sub.empty:
    st.error("After applying coverage and date filters, no scenarios remain.")
    st.stop()

# Portfolio returns per scenario
portfolio_returns = shock_sub.fillna(0).dot(w)

results = (
    portfolio_returns.rename("portfolio_return")
    .reset_index()
    .rename(columns={"index": "scenario"})
    .sort_values("portfolio_return")
)

# Join scenario dates for readability
scenarios_small = scenarios[["scenario", "start_date", "end_date"]].copy()
results = results.merge(scenarios_small, on="scenario", how="left")

# Build display table (2dp)
results_show = results.copy()
results_show["portfolio_return (%)"] = (results_show["portfolio_return"] * 100)

# drop raw decimal return
results_show = results_show.drop(columns=["portfolio_return"])

# reset clean index
results_show = results_show.reset_index(drop=True)

# FORCE 2dp display for st.table (convert to formatted strings)
results_show["portfolio_return (%)"] = results_show["portfolio_return (%)"].map(
    lambda x: f"{x:.2f}" if pd.notna(x) else ""
)

st.subheader("Worst Tail Scenarios")
st.table(results_show)

# Worst N
max_available = min(15, len(results_show))

n = st.slider(
    "Show worst N scenarios",
    min_value=1,
    max_value=max_available,
    value=min(10, max_available)
)

worst_show = results_show.head(n).reset_index(drop=True)
st.subheader(f"Worst {n} scenarios")
st.dataframe(worst_show, use_container_width=True)


# Contribution breakdown
scenario_choice = st.selectbox(
    "Pick a scenario to see asset contributions",
    worst_show["scenario"].tolist() if not worst_show.empty else results_show["scenario"].tolist()
)

asset_returns = shock.loc[scenario_choice, list(w.index)].rename("asset_return")
contrib = (asset_returns * w).rename("contribution")

breakdown = pd.concat([asset_returns, contrib], axis=1).reset_index().rename(columns={"index": "symbol"})

# convert to %
breakdown["asset_return (%)"] = (breakdown["asset_return"] * 100).round(2)
breakdown["contribution (%)"] = (breakdown["contribution"] * 100).round(2)

breakdown = breakdown.drop(columns=["asset_return", "contribution"])
breakdown = breakdown.sort_values("contribution (%)")  # most negative first
breakdown = breakdown.reset_index(drop=True)

st.subheader("Asset-level breakdown")
st.dataframe(breakdown, use_container_width=True)

st.metric("Portfolio return in selected scenario", f"{float(contrib.sum())*100:.2f}%")
