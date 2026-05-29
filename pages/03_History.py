import streamlit as st
import database_sq as db
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Historical Data", layout="wide")

# --- Auth Check ---
if "user" not in st.session_state:
    st.warning("Please login on the Home page first.")
    st.stop()

user_id = st.session_state.user.id

# Verify a portfolio is selected
if "active_portfolio" not in st.session_state or not st.session_state.active_portfolio:
    st.warning("👈 Please select a portfolio on the Home page first.")
    st.stop()

selected_p = st.session_state.active_portfolio
st.title(f"Historical Analysis: {selected_p}")

# Fetch snapshots
snapshots = db.get_historical_snapshots(user_id, selected_p)

if not snapshots:
    st.info("No portfolio snapshots found for the current portfolio. You can generate snapshots by clicking 'Refresh Market Data' on the Dashboard.")
else:
    # Convert to DataFrame
    df = pd.DataFrame(snapshots)
    
    # Ensure timestamp is datetime, handling mixed formats (with/without microseconds) robustly
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601', utc=True, errors='coerce')
    
    # Drop rows where timestamp couldn't be parsed and sort for the chart
    df = df.dropna(subset=['timestamp']).sort_values('timestamp')
    
    st.subheader("Portfolio Value Over Time (Net Liquidity)")
    
    # Create the chart
    fig = px.line(
        df, 
        x="timestamp", 
        y="net_liquidity",
        labels={"net_liquidity": "Net Liquidity ($)", "timestamp": "Date"},
        template="plotly_dark",
        markers=True
    )
    
    # Customizing the chart
    fig.update_traces(line_color='#0971B2')
    fig.update_layout(
        yaxis_tickformat="$,.2f", 
        hovermode="x unified",
        xaxis_title="Snapshot Date",
        yaxis_title="Net Liquidity ($)"
    )
    
    st.plotly_chart(fig, width='stretch')

    # Optional: Display a table of the data
    with st.expander("View Raw Snapshot Data"):
        st.dataframe(df.sort_values("timestamp", ascending=False), width='stretch')
