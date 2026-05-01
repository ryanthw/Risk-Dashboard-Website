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
        title="Portfolio Capital Allocation by Sector",
        color_discrete_sequence=px.colors.sequential.RdBu_r
    )
    st.plotly_chart(fig, width='stretch')

    st.divider()

    # Create two equal columns
    col_strat, col_guard = st.columns(2)

    with col_strat:
        st.subheader("Capital by Strategy")
        if not df.empty:
            strat_df = df.groupby("Type")["Max Loss"].sum().reset_index()
            strat_map = {
                "csp": "Cash Secured Puts", "cc": "Covered Calls",
                "pcs": "Put Credit Spreads", "ccs": "Call Credit Spreads",
                "cds": "Call Debit Spreads", "pds": "Put Debit Spreads",
                "shares": "Long Equity", "short_put": "Naked Puts", "short_call": "Naked Calls"
            }
            strat_df["Strategy Name"] = strat_df["Type"].map(strat_map)

            fig_strat = px.pie(
                strat_df, values="Max Loss", names="Strategy Name",
                hole=0.5, template="plotly_dark", color_discrete_sequence=px.colors.sequential.RdBu_r
            )
            fig_strat.update_traces(textinfo='percent+label')
            fig_strat.update_layout(showlegend=True) 
            st.plotly_chart(fig_strat, width='stretch')

            total_strat_risk = strat_df['Max Loss'].sum()
            st.caption(f"Total Capital at Risk across strategies: ${total_strat_risk:,.2f}")

    with col_guard:
        st.subheader("Ticker Allocation Guard")
        if not df.empty:
            # Calculate % of total risk per ticker
            ticker_df = df.groupby("Ticker")["Max Loss"].sum().reset_index()
            total_risk = ticker_df["Max Loss"].sum()
            ticker_df["% Weight"] = (ticker_df["Max Loss"] / total_risk) * 100
            
            # Sort and display a clean dataframe
            ticker_display = ticker_df.sort_values("% Weight", ascending=False).reset_index(drop=True)
            
            # Style the dataframe: Highlight risk > 10%
            def color_risk(val):
                color = 'red' if val > 10 else 'green'
                return f'color: {color}'

            st.dataframe(
                ticker_display.style.applymap(color_risk, subset=['% Weight']).format({"% Weight": "{:.1f}%", "Max Loss": "${:,.2f}"}),
                width='stretch',
                hide_index=True
            )

            # Quick Status Logic
            limit = 10.0
            if any(ticker_df["% Weight"] > limit):
                st.error(f"⚠️ Concentration Alert: Tickers > {limit}% detected.")
            else:
                st.success(f"✅ Diversification within {limit}% limit.")

    st.divider()
    st.subheader("Portfolio Fulfillment (Target vs. Actual)")

    # Define your model targets (Decimal form)
    TARGETS = {
        "Dividend Engine": 0.25,
        "Income Driver (Wheel)": 0.60,
        "Credit Spreads": 0.10,
        "Cash/Hedges": 0.05
    }

    # --- 1. Define Asset Buckets ---
    core_engine_tickers = ["SCHD", "VIG", "ORC", "MAIN", "AGNC", "ARCC"]

    # Filter Dataframe for Strategy Buckets
    # Core Engine: Specific tickers held as shares
    engine_df = df[(df["Type"] == "shares") & (df["Ticker"].isin(core_engine_tickers))]

    # Income Driver: CSPs, CCs, AND shares NOT in the core engine (assigned stock)
    driver_df = df[
        (df["Type"].isin(["csp", "cc", "short_put", "short_call"])) | 
        ((df["Type"] == "shares") & (~df["Ticker"].isin(core_engine_tickers)))
    ]

    # High-Yield Spreads
    spread_df = df[df["Type"].isin(["pcs", "ccs", "cds", "pds"])]

    available_cash = utils.get_undeployed_cash(selected_p)

    # --- 2. Calculate Actual Percentages ---
    # We use port_val (Total Value) as the denominator for the "Income Factory" model
    actual_engine = engine_df["Max Loss"].sum() / port_val if port_val > 0 else 0
    actual_driver = driver_df["Max Loss"].sum() / port_val if port_val > 0 else 0
    actual_spread = spread_df["Max Loss"].sum() / port_val if port_val > 0 else 0
    actual_cash = available_cash / port_val if port_val > 0 else 0

    # 2. Render Fulfillment Bars
    def render_fulfillment(label, actual, target):
        progress = min(actual / target, 1.0) if target > 0 else 0
        col_label, col_bar, col_metric = st.columns([1, 2, 1])
        col_label.write(f"**{label}**")
        col_bar.progress(progress)
        delta = (actual - target) * 100
        col_metric.metric("Actual", f"{actual*100:.1f}%", f"{delta:.1f}% vs Target")

    render_fulfillment("Core Engine (Div/mREIT)", actual_engine, TARGETS["Dividend Engine"])
    render_fulfillment("Income Driver (Wheel)", actual_driver, TARGETS["Income Driver (Wheel)"])
    render_fulfillment("Credit Spreads", actual_spread, TARGETS["Credit Spreads"])
    render_fulfillment("Cash", actual_cash, TARGETS["Cash/Hedges"])