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
@st.cache_resource
def get_ib(host: str, port: int):
    """
    Connect to IBKR using a stable default clientId.
    If the clientId is already in use, fall back to another one automatically.
    """
    ib = IB()
    for cid in [1, 2, 3, 10, 11, 12, 13, 99]:
        try:
            ib.connect(host, int(port), clientId=int(cid), timeout=5)
            st.session_state["ib_client_id_used"] = cid
            return ib
        except Exception:
            pass
    raise RuntimeError("Unable to connect to IBKR. All fallback clientIds are in use or connection failed.")


def fetch_positions_with_weights(ib: IB, shock_cols: set, mode: str = "gross") -> pd.DataFrame:
    """
    Returns DataFrame with:
      asset (unique label for display),
      shock_key (column used to look up shocks),
      weight (computed on position_value)
    """
    pos = ib.positions()
    rows = []

    for p in pos:
        c = p.contract

        sym = str(getattr(c, "symbol", "")).upper().strip()
        sym_base = sym.split(".")[0]  
        ccy = str(getattr(c, "currency", "")).upper().strip()
        exch = str(getattr(c, "exchange", "")).upper().strip()
        local = getattr(c, "localSymbol", None)
        local = str(local).upper().strip() if local else ""
        sec_type = getattr(c, "secType", None)

        # ---- DISPLAY KEY (unique-ish per position) ----
        # Futures localSymbol includes expiry (ESM6), so it stays unique.
        # Stocks use SYMBOL__CCY so MSFT USD vs CAD become different display assets.
        asset = local if local else f"{sym_base}__{ccy}"

        # ---- SHOCK LOOKUP KEY (must match shock_matrix columns) ----
        # Futures: map contract (ESM6) -> underlying symbol (ES)
        # Stocks: use SYMBOL__CCY if your shock matrix supports it; else fallback to SYMBOL.
        if sec_type == "FUT":
            shock_key = sym_base
        else:
            key_ccy = f"{sym_base}__{ccy}"
            shock_key = key_ccy if key_ccy in shock_cols else sym_base

        # approximate position value
        mv = None
        if hasattr(p, "marketValue") and p.marketValue is not None:
            try:
                mv = float(p.marketValue)
            except Exception:
                mv = None
        if mv is None:
            mv = float(p.position) * float(p.avgCost)

        rows.append({
            "asset": asset,
            "shock_key": shock_key,
            "symbol": sym_base,
            "sec_type": sec_type,
            "exchange": exch,
            "currency": ccy,
            "quantity": float(p.position),
            "avg_cost": float(p.avgCost),
            "position_value": float(mv),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df[df["position_value"].notna() & (df["position_value"] != 0)].copy()

    # weights
    if mode == "gross":
        denom = df["position_value"].abs().sum()
    else:
        denom = df["position_value"].sum()

    df["weight"] = np.nan if denom == 0 else (df["position_value"] / denom)
    df = df.sort_values("weight", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)
    return df


# ---------- UI ----------
st.title("Portfolio Tail-Risk Stress Test")
st.caption("Pulls local IBKR positions and applies historical crisis shocks (scenario × asset returns).")

shock_cols = set(shock.columns.astype(str))

# Load from IBKR
if st.button("Load portfolio from IBKR", key="load_ibkr_btn"):
    try:
        ib = get_ib(host, port)
        used = st.session_state.get("ib_client_id_used", "unknown")
        st.info(f"Connected to IBKR (clientId={used}). Fetching positions...")

        pf_full = fetch_positions_with_weights(ib, shock_cols=shock_cols, mode=weight_mode)
        st.session_state["pf_full"] = pf_full
        st.success("Loaded positions from IBKR.")
    except Exception as e:
        st.error(f"Failed to connect or fetch positions: {e}")

pf_full = st.session_state.get("pf_full")

if pf_full is None or pf_full.empty:
    st.info("Click **Load portfolio from IBKR** to pull positions.")
    st.stop()

# ---------- Display positions ----------
st.subheader("IBKR Positions (derived weights)")

pf_show = pf_full.copy()
pf_show["weight (%)"] = (pf_show["weight"] * 100).round(2)
pf_show = pf_show.drop(columns=["weight"])

for col in ["avg_cost", "position_value"]:
    pf_show[col] = pf_show[col].round(2)

pf_show = pf_show[["asset", "shock_key", "symbol", "sec_type", "exchange", "currency", "quantity", "avg_cost", "position_value", "weight (%)"]]
st.dataframe(pf_show, use_container_width=True)

# --- Build portfolio detail (POSITION-level, keep duplicates like MSFT) ---
portfolio = pf_full[["asset", "shock_key", "symbol", "exchange", "currency", "weight"]].copy()

# Check availability in shock matrix
shock_cols = set(shock.columns.astype(str))

# If shock_key missing but base symbol exists, FALL BACK to symbol (keeps row)
missing_keys = portfolio.loc[~portfolio["shock_key"].isin(shock_cols), "shock_key"].unique().tolist()

fallback_mask = (~portfolio["shock_key"].isin(shock_cols)) & (portfolio["symbol"].isin(shock_cols))
portfolio.loc[fallback_mask, "shock_key"] = portfolio.loc[fallback_mask, "symbol"]

portfolio["has_data"] = portfolio["shock_key"].isin(shock_cols)

still_missing = portfolio.loc[~portfolio["has_data"], "shock_key"].unique().tolist()
if missing_keys:
    st.warning(
        f"Shock matrix missing these columns (some may be auto-mapped to base symbol): {missing_keys}\n\n"
        f"Still missing (will contribute 0 / NaN): {still_missing}"
    )

portfolio_ok = portfolio.copy()
portfolio_used = portfolio_ok[portfolio_ok["has_data"]].copy()

if portfolio_used.empty:
    st.error("None of the portfolio positions map to shock matrix columns.")
    st.stop()

# Normalize weights at POSITION level (so split contributions stay correct)
if normalize_weights:
    denom = portfolio_used["weight"].abs().sum()
    if denom != 0:
        portfolio_used["weight"] = portfolio_used["weight"] / denom

# Portfolio returns: aggregate weights by shock_key (since shock matrix is keyed by columns)
w_key = portfolio_used.groupby("shock_key")["weight"].sum()

shock_sub = shock[list(w_key.index)].copy()

# Coverage filter (drop scenarios with too few non-null assets)
coverage = shock_sub.notna().sum(axis=1)
shock_sub = shock_sub.loc[coverage >= int(min_assets_required)].copy()

if shock_sub.empty:
    st.error("After applying coverage and date filters, no scenarios remain.")
    st.stop()

# Portfolio returns per scenario
portfolio_returns = shock_sub.fillna(0).dot(w_key)


results = (
    portfolio_returns.rename("portfolio_return")
    .reset_index()
    .rename(columns={"index": "scenario"})
    .sort_values("portfolio_return")
)

# Join scenario dates for readability
scenarios_small = scenarios[["scenario", "start_date", "end_date"]].copy()
results = results.merge(scenarios_small, on="scenario", how="left")

# Build display table (force 2dp display for st.table)
results_show = results.copy()
results_show["portfolio_return (%)"] = (results_show["portfolio_return"] * 100).map(
    lambda x: f"{x:.2f}" if pd.notna(x) else ""
)
results_show = results_show.drop(columns=["portfolio_return"]).reset_index(drop=True)

st.subheader("Worst Tail Scenarios")
st.table(results_show)

# Worst N
max_available = min(15, len(results_show))
n = st.slider("Show worst N scenarios", 1, max_available, min(10, max_available))

worst_show = results_show.head(n).reset_index(drop=True)
st.subheader(f"Worst {n} scenarios")
st.dataframe(worst_show, use_container_width=True)

# Contribution breakdown
scenario_choice = st.selectbox(
    "Pick a scenario to see asset contributions",
    worst_show["scenario"].tolist() if not worst_show.empty else results_show["scenario"].tolist()
)

breakdown = portfolio_ok[["asset", "shock_key", "symbol", "exchange", "currency", "weight"]].copy()
BASE_CCY = "USD"

def get_shock_return(key: str) -> float:
    if key in shock.columns:
        return float(shock.loc[scenario_choice, key])
    return np.nan

def get_fx_return(ccy: str, base: str = BASE_CCY) -> float:
    if (not ccy) or (ccy == base):
        return 0.0

    direct = f"{ccy}{base}"   # e.g. CADUSD
    inverse = f"{base}{ccy}"  # e.g. USDCAD

    if direct in shock.columns:
        return float(shock.loc[scenario_choice, direct])

    if inverse in shock.columns:
        inv = shock.loc[scenario_choice, inverse]
        if pd.isna(inv):
            return np.nan
        inv = float(inv)
        return (1.0 / (1.0 + inv)) - 1.0

    return np.nan  # FX not available

def position_return(row) -> float:
    eq = get_shock_return(row["shock_key"])
    if pd.isna(eq):
        return np.nan
    fx = get_fx_return(row["currency"], base=BASE_CCY)
    if pd.isna(fx):
        return eq  # if no FX series, fall back to equity-only
    return (1.0 + eq) * (1.0 + fx) - 1.0

breakdown["asset_return"] = breakdown.apply(position_return, axis=1)
breakdown["contribution"] = breakdown["asset_return"] * breakdown["weight"]

breakdown["asset_return (%)"] = (breakdown["asset_return"] * 100).round(2)
breakdown["contribution (%)"] = (breakdown["contribution"] * 100).round(2)

breakdown = breakdown.drop(columns=["asset_return", "contribution"])
breakdown = breakdown[["asset", "shock_key", "symbol", "exchange", "currency", "asset_return (%)", "contribution (%)"]]
breakdown = breakdown.sort_values("contribution (%)").reset_index(drop=True)

st.subheader("Asset-level breakdown")
st.dataframe(breakdown, use_container_width=True)

portfolio_return_selected = np.nansum(breakdown["contribution (%)"].values)
st.metric("Portfolio return in selected scenario", f"{portfolio_return_selected:.2f}%")
