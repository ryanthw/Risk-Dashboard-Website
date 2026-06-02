import streamlit as st
import database_sq as db
import utils
import plotly.express as px
import plotly.figure_factory as ff
import pandas as pd
import numpy as np

st.set_page_config(page_title="Portfolio Visuals", layout="wide")

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
st.title(f"Visual Analysis: {selected_p}")

trades = db.get_trades(user_id, selected_p)

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
            "Exp": t.expiration,
            "Risk": abs(t.max_loss), 
            "Portfolio-Risk(%)": utils.get_percent_risk_position(user_id, t, selected_p)
        })
    df = pd.DataFrame(data)

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        st.subheader("Risk-Reward Profile")
        fig_scatter = px.scatter(
            df, x="Max Loss", y="Max Gain", size="POP", color="Ticker",
            hover_name="Ticker", template="plotly_dark"
        )
        st.plotly_chart(fig_scatter, width="content")

    with col2:
        st.subheader("Options Capital at Risk")
        options_only_df = df.query("Type != 'shares'")
        
        if not options_only_df.empty:
            fig_bar = px.bar(
                options_only_df, x="Exp", y="Risk", color="Ticker", 
                template="plotly_dark", barmode="group",
                labels={"Risk": "Max Loss ($)", "Exp": "Expiration Date"}
            )
            st.plotly_chart(fig_bar, width="content")
        else:
            st.info("No option trades to display.")

    with col3:
        st.subheader("Portfolio Risk Allocation")
        fig_pie = px.pie(
            df, values="Risk", names="Ticker",
            hole=0.4, 
            template="plotly_dark",
            color_discrete_sequence=px.colors.sequential.RdBu_r
        )
        fig_pie.update_traces(textinfo='percent+label')
        fig_pie.update_layout(showlegend=False) 
        st.plotly_chart(fig_pie, width="content")

if trades:
    st.subheader("Portfolio Aggregated P&L Distribution")

    all_sims = [np.array(t.pnl_dist) for t in trades if t.trade_type not in ["shares"]]

    if all_sims:
        portfolio_sims = np.sum(all_sims, axis=0)

        avg_pnl = np.mean(portfolio_sims)
        std_dev = np.std(portfolio_sims)
        prob_profit = (portfolio_sims > 0).mean() * 100

        m1, m2, m3 = st.columns(3)
        m1.metric("Agg. Expected Return", f"${avg_pnl:,.2f}")
        m2.metric("Portfolio Std Dev", f"${std_dev:,.2f}")
        m3.metric("Portfolio POP", f"{prob_profit:.1f}%")

        plot_data = portfolio_sims[::10] 
        
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
        
        fig.add_vline(x=0, line_dash="dash", line_color="red", annotation_text="Break-Even")

        st.plotly_chart(fig, width="stretch")
        st.caption("Note: Stock pnl_distributions are not included due to long time horizon and skew factors. This represents an options-only view.")
    else:
        st.warning("No simulation data found. Try refreshing market data on the Dashboard.")

def render_advanced_risk_analytics(trades):
    st.divider()
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("Portfolio Stress Test Matrix")
        
        price_shifts = np.linspace(-0.15, 0.15, 14) # -15% to +15%
        vol_shifts = np.linspace(-0.10, 0.30, 10)   # -10% to +30%
        
        z_data = []
        for v_shift in vol_shifts:
            row = []
            for p_shift in price_shifts:
                total_pnl = 0.0
                for t in trades:
                    v0 = t.get_theoretical_value()
                    v_shock = t.get_theoretical_value(
                        S=t.underlying_price * (1 + p_shift),
                        iv=t.iv + v_shift
                    )
                    total_pnl += (v_shock - v0)
                row.append(total_pnl)
            z_data.append(row)
            
        fig = px.imshow(
            z_data,
            x=[f"{p*100:+.1f}%" for p in price_shifts],
            y=[f"{v*100:+.0f}%" for v in vol_shifts],
            labels=dict(x="Price Shift", y="Vol Shift", color="P&L ($)"),
            color_continuous_scale="RdYlGn",
            aspect="auto",
            template="plotly_dark"
        )
        st.plotly_chart(fig, width="stretch")
        st.caption("Estimated P&L impact given simultaneous price and volatility shocks.")

    with col_right:
        st.subheader("Greek Surface (30-Day Decay)")
        
        days_out = np.arange(0, 31)
        theta_decay = []
        vega_decay = []
        
        for d in days_out:
            t_theta = 0.0
            t_vega = 0.0
            for t in trades:
                if t.trade_type == "shares": continue
                
                T_new = max(0, (t.dte - d) / 365.0)
                # Recalculate greeks at future time T
                v0 = t.get_theoretical_value(T=T_new)
                
                # Vega (1% vol shift)
                dv = 0.01
                v_up_v = t.get_theoretical_value(T=T_new, iv=t.iv + dv)
                vega = (v_up_v - v0) / (dv * 100)
                
                # Theta (Daily)
                dt = 1.0 / 365.0
                v_next = t.get_theoretical_value(T=max(0, T_new - dt))
                theta = (v_next - v0)
                
                t_theta += theta
                t_vega += vega
            
            theta_decay.append(t_theta)
            vega_decay.append(t_vega)
            
        df_decay = pd.DataFrame({
            "Days from Now": days_out,
            "Total Theta": theta_decay,
            "Total Vega": vega_decay
        })
        
        fig = px.line(
            df_decay, x="Days from Now", y=["Total Theta", "Total Vega"],
            title="Portfolio Greek Decay Over Time",
            template="plotly_dark",
            labels={"value": "Risk Exposure ($)", "variable": "Greek"}
        )
        st.plotly_chart(fig, width="stretch")
        st.caption("How your portfolio's Theta income and Vega risk change as expirations approach.")

if trades:
    render_advanced_risk_analytics(trades)

def render_compounding_chart(user_id, trades, port_val):
    st.subheader("10-Year Wealth Forecast")
    
    annual_rate = utils.get_er_ann(user_id, selected_p)
    if not annual_rate or port_val <= 0:
        st.info("Add risk-defined trades to generate a forecast.")
        return

    years = np.arange(0, 11)
    forecast_values = port_val * (1 + annual_rate) ** years
    conservative_rate = annual_rate * 0.7
    cons_values = port_val * (1 + conservative_rate) ** years
    
    df_forecast = pd.DataFrame({
        "Year": years,
        "Target Projection": forecast_values,
        "Conservative (70%)": cons_values
    })

    fig = px.line(
        df_forecast, x="Year", y=["Target Projection", "Conservative (70%)"],
        title=f"Projected Growth (Target: {annual_rate*100:.1f}%)",
        labels={"value": "Account Balance ($)", "variable": "Scenario"},
        color_discrete_map={
            "Target Projection": "#00CC96", 
            "Conservative (70%)": "#636EFA"  
        }
    )
    
    fig.update_traces(patch={"line": {"dash": "dash"}}, selector={"name": "Conservative (70%)"})
    fig.update_layout(yaxis_tickformat="$,.0f", hovermode="x unified")
    
    st.plotly_chart(fig, width="stretch")
    
    st.caption(f"Note: Target assumes 100% win rate and full capital reinvestment. "
               f"Conservative assumes a realization of {conservative_rate*100:.1f}% APR.")

if trades:
    render_compounding_chart(user_id, trades, db.get_portfolio_val(user_id, selected_p))
