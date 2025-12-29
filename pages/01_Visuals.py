import streamlit as st
import database_sq as db
import utils
import plotly.express as px
import plotly.figure_factory as ff
import pandas as pd
import numpy as np

st.set_page_config(page_title="Portfolio Visuals", layout="wide")

# Verify a portfolio is selected
if "active_portfolio" not in st.session_state or not st.session_state.active_portfolio:
    st.warning("👈 Please select a portfolio on the Home page first.")
    st.stop()

selected_p = st.session_state.active_portfolio
st.title(f"Visual Analysis: {selected_p}")

trades = db.get_trades(selected_p)

if not trades:
    st.info("No trades found to visualize.")
else:
    # Prepare data for plotting
    data = []
    for t in trades:
        data.append({
            "Ticker": t.ticker,
            "Max Loss": t.max_loss,
            "Max Gain": t.max_gain,
            "POP": t.pop * 100,
            "Type": t.trade_type,
            "Exp": t.expiration
        })
    df = pd.DataFrame(data)

    # Layout for Plots
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Risk-Reward Profile")
        fig_scatter = px.scatter(
            df, x="Max Loss", y="Max Gain", size="POP", color="Ticker",
            hover_name="Ticker", template="plotly_dark"
        )
        st.plotly_chart(fig_scatter, width="stretch")

    with col2:
        st.subheader("Capital at Risk by Expiration")
        fig_bar = px.bar(
            df, x="Exp", y="Max Loss", color="Ticker", 
            template="plotly_dark", barmode="group"
        )
        st.plotly_chart(fig_bar, width="stretch")

trades = db.get_trades(selected_p)

if trades:
    st.subheader("Portfolio Aggregated P&L Distribution")

    # 1. Collect all simulation arrays
    # Assuming each t.pnl_dist is a numpy array of length 100,000
    all_sims = [np.array(t.pnl_dist) for t in trades]

    if all_sims:
        # 2. Sum the simulations element-wise
        # This represents the portfolio's outcome across 100,000 different scenarios
        portfolio_sims = np.sum(all_sims, axis=0)

        # 3. Calculate Aggregate Stats
        avg_pnl = np.mean(portfolio_sims)
        std_dev = np.std(portfolio_sims)
        prob_profit = (portfolio_sims > 0).mean() * 100

        # Display Summary Stats
        m1, m2, m3 = st.columns(3)
        m1.metric("Agg. Expected Return", f"${avg_pnl:,.2f}")
        m2.metric("Portfolio Std Dev", f"${std_dev:,.2f}")
        m3.metric("Portfolio POP", f"{prob_profit:.1f}%")

        # 4. Create the Distribution Plot (Histogram + KDE)
        # Using a subset of data for faster rendering if sims are very large
        plot_data = portfolio_sims[::10] # Sample every 10th result for speed
        
        fig = ff.create_distplot(
            [plot_data], 
            group_labels=["Portfolio Total P&L"], 
            bin_size=[std_dev/10],
            show_hist=True,
            show_curve=True,
            colors=['#0971B2']
        )
        
        fig.update_layout(
            title_text="Monte Carlo Portfolio Simulation",
            xaxis_title="P&L at Expiration ($)",
            yaxis_title="Probability Density",
            showlegend=False
        )
        
        # Add a vertical line for the Break-Even (0)
        fig.add_vline(x=0, line_dash="dash", line_color="red", annotation_text="Break-Even")

        st.plotly_chart(fig, width="stretch")
    else:
        st.warning("No simulation data found. Try refreshing market data on the Dashboard.")

def render_compounding_chart(trades, port_val):
    st.subheader("10-Year Wealth Forecast")
    
    if not trades or port_val <= 0:
        st.info("Add trades and cash to see compounding forecasts.")
        return

    # 1. Calculate weighted average return per "cycle"
    total_expected_return = sum(t.expected_profit for t in trades if t.trade_type != "shares")
    avg_dte = sum(t.dte for t in trades if t.trade_type != "shares") / len(trades) if trades else 30
    
    # 2. Annualize the return
    # If a portfolio makes 2% every 30 days, annual return = (1 + 0.02)^(365/30) - 1
    return_per_cycle = total_expected_return / port_val
    cycles_per_year = 365 / max(avg_dte, 1)
    annual_rate = (1 + return_per_cycle) ** cycles_per_year - 1
    
    # 3. Generate 20-year projection
    years = np.arange(0, 11)
    # Compound Interest Formula: A = P(1 + r)^t
    forecast_values = port_val * (1 + annual_rate) ** years
    
    df_forecast = pd.DataFrame({
        "Year": years,
        "Projected Value": forecast_values
    })

    # 4. Create the Chart
    fig = px.line(
        df_forecast, x="Year", y="Projected Value",
        title=f"Projected Growth @ {annual_rate*100:.1f}% Annualized",
        labels={"Projected Value": "Account Balance ($)"}
    )
    
    # Add a marker for the current value
    fig.add_scatter(x=[0], y=[port_val], mode="markers", name="Starting Balance", marker=dict(size=12, color="green"))
    
    # Format Y-axis as currency
    fig.update_layout(yaxis_tickformat="$,.0f")
    
    st.plotly_chart(fig, width="stretch")
    
    # Contextual Summary
    st.write(f"Based on your current positions, your portfolio is generating an expected **{return_per_cycle*100:.2f}%** per **{avg_dte:.0f} days**.")

if trades:
    render_compounding_chart(trades, db.get_portfolio_val(selected_p))