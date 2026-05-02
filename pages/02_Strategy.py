import streamlit as st
import database_sq as db
import utils
import pandas as pd
import plotly.express as px
import yfinance as yf
import numpy as np
import plotly.figure_factory as ff

st.set_page_config(page_title="PM Strategy", layout="wide")

# 1. Verification
if "active_portfolio" not in st.session_state or not st.session_state.active_portfolio:
    st.warning("👈 Please select a portfolio on the Home page first.")
    st.stop()

selected_p = st.session_state.active_portfolio
st.title(f"PM Strategy & Allocation: {selected_p}")

# 2. Data Loading & Pre-processing
trades = db.get_trades(selected_p)
port_val = db.get_portfolio_val(selected_p)

if not trades:
    st.info("No trades found. Add positions to see PM analytics.")
    st.stop()

# Prepare Core DataFrame
data = []
for t in trades:
    data.append({
        "Ticker": t.ticker,
        "Sector": getattr(t, 'sector', 'Unknown'),
        "Max Loss": t.max_loss,
        "Type": t.trade_type,
        "Expected Profit": t.expected_profit,
        "DTE": max(getattr(t, 'dte', 1), 1)
    })
df = pd.DataFrame(data)

# --- ADVANCED MATH (Upfront for Vitals) ---
tickers = list(set(df["Ticker"].tolist()))
hist_data = yf.download(tickers, period="6mo", progress=False)['Close']
returns = hist_data.pct_change().dropna()
corr_matrix = returns.corr()

# Calculate Anti-Correlation Score
ticker_risk = df.groupby("Ticker")["Max Loss"].sum()
total_risk = ticker_risk.sum()
weights = (ticker_risk / total_risk).to_dict()

weighted_corr_sum = 0
weight_product_sum = 0
high_corr_flags = []
matrix_tickers = list(corr_matrix.columns)

for i in range(len(matrix_tickers)):
    for j in range(i + 1, len(matrix_tickers)):
        t1, t2 = matrix_tickers[i], matrix_tickers[j]
        correlation = corr_matrix.loc[t1, t2]
        w1, w2 = weights.get(t1, 0), weights.get(t2, 0)
        weighted_corr_sum += correlation * (w1 * w2)
        weight_product_sum += (w1 * w2)
        if correlation > 0.75:
            high_corr_flags.append({"Pair": f"{t1} & {t2}", "Correlation": correlation, "Risk Impact (%)": (w1+w2)*100})

avg_corr = weighted_corr_sum / weight_product_sum if weight_product_sum > 0 else 0
anti_corr_score = 1 - avg_corr

# Calculate Vitals
beta_delta = utils.get_portfolio_beta_delta(selected_p)
total_theta = sum([row['Expected Profit'] / row['DTE'] for idx, row in df.iterrows() if row['Type'] != 'shares'])

# --- SECTION 1: INSTITUTIONAL HEALTH VITALS ---
st.divider()
v1, v2, v3 = st.columns(3)
v1.metric("Anti-Correlation Score", f"{anti_corr_score:.2f}", help="Diversification Rating (Goal > 0.60)")
v2.metric("Beta-Weighted Delta", f"{beta_delta:.1f}", delta="Bullish Bias" if beta_delta > 0 else "Bearish Bias")
v3.metric("Daily Income (Est. Theta)", f"${total_theta:.2f}", help="Daily value decay of option positions")

# --- SECTION 2: SECTOR & STRATEGY ---
st.divider()
st.subheader("Structural Allocation")
fig_tree = px.treemap(
    df, path=['Sector', 'Ticker'], values='Max Loss', color='Sector',
    template="plotly_dark", title="Capital Allocation by Sector",
    color_discrete_sequence=px.colors.sequential.RdBu_r
)
st.plotly_chart(fig_tree, width='stretch')

col_strat, col_guard = st.columns(2)

with col_strat:
    st.subheader("Capital by Strategy")
    strat_df = df.groupby("Type")["Max Loss"].sum().reset_index()
    strat_map = {
        "csp": "Cash Secured Puts", "cc": "Covered Calls",
        "pcs": "Put Credit Spreads", "ccs": "Call Credit Spreads",
        "cds": "Call Debit Spreads", "pds": "Put Debit Spreads",
        "shares": "Long Equity", "short_put": "Naked Puts", "short_call": "Naked Calls"
    }
    strat_df["Strategy Name"] = strat_df["Type"].map(strat_map)
    fig_pie = px.pie(
        strat_df, values="Max Loss", names="Strategy Name",
        hole=0.5, template="plotly_dark", color_discrete_sequence=px.colors.sequential.RdBu_r
    )
    fig_pie.update_traces(textinfo='percent+label')
    st.plotly_chart(fig_pie, width='stretch')

with col_guard:
    st.subheader("Ticker Allocation Guard")
    ticker_df = df.groupby("Ticker")["Max Loss"].sum().reset_index()
    ticker_df["% Weight"] = (ticker_df["Max Loss"] / total_risk) * 100
    ticker_display = ticker_df.sort_values("% Weight", ascending=False).reset_index(drop=True)
    
    def color_risk(val):
        return 'color: red' if val > 10 else 'color: green'

    st.dataframe(
        ticker_display.style.applymap(color_risk, subset=['% Weight']).format({"% Weight": "{:.1f}%", "Max Loss": "${:,.2f}"}),
        width='stretch', hide_index=True
    )
    if any(ticker_df["% Weight"] > 10):
        st.error("⚠️ Concentration Alert: Tickers > 10% detected.")
    else:
        st.success("✅ Diversification within 10% limit.")

# --- SECTION 3: FULFILLMENT ---
st.divider()
st.subheader("🎯 Income Factory Fulfillment")
TARGETS = {"Dividend Engine": 0.25, "Income Driver (Wheel)": 0.60, "Credit Spreads": 0.10, "Cash/Hedges": 0.05}
core_engine_tickers = ["SCHD", "VIG", "ORC", "MAIN", "AGNC", "ARCC"]

engine_risk = df[(df["Type"] == "shares") & (df["Ticker"].isin(core_engine_tickers))]["Max Loss"].sum()
driver_risk = df[(df["Type"].isin(["csp", "cc", "short_put", "short_call"])) | ((df["Type"] == "shares") & (~df["Ticker"].isin(core_engine_tickers)))]["Max Loss"].sum()
spread_risk = df[df["Type"].isin(["pcs", "ccs", "cds", "pds"])]["Max Loss"].sum()
actual_cash = utils.get_undeployed_cash(selected_p)

def render_fulfillment(label, actual_val, target_pct):
    actual_pct = actual_val / port_val if port_val > 0 else 0
    progress = min(actual_pct / target_pct, 1.0)
    c1, c2, c3 = st.columns([1, 2, 1])
    c1.write(f"**{label}**")
    c2.progress(progress)
    c3.metric("Actual", f"{actual_pct*100:.1f}%", f"{(actual_pct-target_pct)*100:.1f}% vs Target")

render_fulfillment("Core Engine", engine_risk, TARGETS["Dividend Engine"])
render_fulfillment("Income Driver", driver_risk, TARGETS["Income Driver (Wheel)"])
render_fulfillment("Credit Spreads", spread_risk, TARGETS["Credit Spreads"])
render_fulfillment("Cash", actual_cash, TARGETS["Cash/Hedges"])

# --- SECTION 4: CORRELATION ---
st.divider()
st.subheader("Anti-Correlation Analysis")
fig_heat = ff.create_annotated_heatmap(
    z=corr_matrix.values, x=list(corr_matrix.columns), y=list(corr_matrix.index),
    colorscale='RdBu', zmin=-1, zmax=1
)
st.plotly_chart(fig_heat, width='stretch')

if high_corr_flags:
    st.warning("⚠️ **High Correlation Flags**")
    st.dataframe(pd.DataFrame(high_corr_flags), width='stretch', hide_index=True)