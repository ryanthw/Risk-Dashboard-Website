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
    all_sims = [np.array(t.pnl_dist) for t in trades if t.trade_type != "shares"]

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
        st.caption("Note: Stock pnl_distributions are not included due to long time horizon and skew factors. This represents an options-only view.")
    else:
        st.warning("No simulation data found. Try refreshing market data on the Dashboard.")

def render_compounding_chart(trades, port_val):
    st.subheader("10-Year Wealth Forecast")
    
    annual_rate = utils.get_er_ann(selected_p)
    if not annual_rate or port_val <= 0:
        st.info("Add risk-defined trades to generate a forecast.")
        return

    years = np.arange(0, 11)
    
    # 1. Standard Forecast (Target)
    forecast_values = port_val * (1 + annual_rate) ** years
    
    # 2. Conservative Forecast (70% of Target Rate)
    # This accounts for the 'slippage' between math and reality
    conservative_rate = annual_rate * 0.7
    cons_values = port_val * (1 + conservative_rate) ** years
    
    df_forecast = pd.DataFrame({
        "Year": years,
        "Target Projection": forecast_values,
        "Conservative (70%)": cons_values
    })

    # 3. Create the Chart
    fig = px.line(
        df_forecast, x="Year", y=["Target Projection", "Conservative (70%)"],
        title=f"Projected Growth (Target: {annual_rate*100:.1f}%)",
        labels={"value": "Account Balance ($)", "variable": "Scenario"},
        color_discrete_map={
            "Target Projection": "#00CC96", # Green
            "Conservative (70%)": "#636EFA"  # Blue/Gray
        }
    )
    
    # Stylize the conservative line as dashed
    fig.update_traces(patch={"line": {"dash": "dash"}}, selector={"name": "Conservative (70%)"})
    fig.update_layout(yaxis_tickformat="$,.0f", hovermode="x unified")
    
    st.plotly_chart(fig, width="stretch")
    
    st.caption(f"Note: Target assumes 100% win rate and full capital reinvestment. "
               f"Conservative assumes a realization of {conservative_rate*100:.1f}% APR.")

if trades:
    render_compounding_chart(trades, db.get_portfolio_val(selected_p))