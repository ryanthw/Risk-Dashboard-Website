import streamlit as st
import database_sq as db
import utils
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="PM Strategy", layout="wide")

# 1. Verification (Same as your Visuals page)
if "active_portfolio" not in st.session_state or not st.session_state.active_portfolio:
    st.warning("👈 Please select a portfolio on the Home page first.")
    st.stop()

selected_p = st.session_state.active_portfolio
st.title(f"PM & Allocation: {selected_p}")

# 2. Load Data
trades = db.get_trades(selected_p)
port_val = db.get_portfolio_val(selected_p)

if not trades:
    st.info("No trades found. Add positions to see PM analytics.")
    st.stop()

if trades:
    # Prepare DataFrame for Treemap
    data = []
    for t in trades:
        data.append({
            "Ticker": t.ticker,
            "Sector": getattr(t, 'sector', 'Unknown'), # Use getattr for old trades
            "Max Loss": t.max_loss,
            "Type": t.trade_type
        })
    df = pd.DataFrame(data)

    st.subheader("Sector Exposure (Risk-Based)")
    # Treemap visually groups Tickers inside their respective Sectors
    fig = px.treemap(
        df, 
        path=['Sector', 'Ticker'], 
        values='Max Loss',
        color='Sector',
        template="plotly_dark",
        title="Portfolio Capital Allocation by Sector"
    )
    st.plotly_chart(fig, width='stretch')