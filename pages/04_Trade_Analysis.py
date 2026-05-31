import streamlit as st
import database_sq as db
import api_interactions as api
import utils
from trade import Trade
from datetime import datetime, timedelta
import time
import plotly.graph_objects as objects
import numpy as np
import scipy.stats as stats

st.set_page_config(page_title="Trade Analysis", layout="wide")

# --- Auth Check ---
if "user" not in st.session_state:
    st.warning("Please login on the Home page first.")
    st.stop()

user_id = st.session_state.user.id
selected_p = st.session_state.get("active_portfolio")

# --- 10-Minute Caching Logic ---
if "draft_trade" not in st.session_state:
    st.session_state.draft_trade = {
        "ticker": "",
        "trade_type": "shares",
        "qty": 1,
        "strike": 0.0,
        "strike_2": 0.0,
        "premium": 0.0,
        "iv": 0.20,
        "expiration": datetime.now().date() + timedelta(days=30),
        "last_updated": time.time()
    }

def update_draft_time():
    st.session_state.draft_trade["last_updated"] = time.time()

# Check TTL
if time.time() - st.session_state.draft_trade["last_updated"] > 600:
    st.session_state.draft_trade = {
        "ticker": "",
        "trade_type": "shares",
        "qty": 1,
        "strike": 0.0,
        "strike_2": 0.0,
        "premium": 0.0,
        "iv": 0.20,
        "expiration": datetime.now().date() + timedelta(days=30),
        "last_updated": time.time()
    }

st.title("Trade Analysis Sandbox")
st.write("Simulate a trade and see its impact before execution.")

# --- Layout: Inputs (Left) and Metrics (Right) ---
col_in, col_met = st.columns([0.3, 0.7])

with col_in:
    st.subheader("Trade Configuration")
    
    t_type = st.selectbox("Trade Type", [
        "shares", "csp", "cc", "short_call", "short_put", 
        "long_call", "long_put", "pcs", "ccs", "cds", "pds"
    ], index=["shares", "csp", "cc", "short_call", "short_put", 
              "long_call", "long_put", "pcs", "ccs", "cds", "pds"].index(st.session_state.draft_trade["trade_type"]))
    
    ticker = st.text_input("Ticker", value=st.session_state.draft_trade["ticker"]).upper()
    
    # Auto-fetch price/IV if ticker changed
    if ticker != st.session_state.draft_trade["ticker"] and ticker:
        with st.spinner(f"Fetching data for {ticker}..."):
            price = api.get_price(ticker)
            iv = api.get_historical_volatility(ticker) if t_type == "shares" else 0.25 # Default IV for options analysis
            st.session_state.draft_trade["ticker"] = ticker
            st.session_state.draft_trade["iv"] = iv
            st.session_state.draft_trade["underlying_price"] = price
            update_draft_time()
            st.rerun()

    qty = st.number_input("Quantity", min_value=1, value=st.session_state.draft_trade["qty"])
    
    col1, col2 = st.columns(2)
    strike = col1.number_input("Strike 1", value=float(st.session_state.draft_trade["strike"]))
    
    is_spread = t_type in ["pcs", "ccs", "cds", "pds"]
    strike_2 = 0.0
    if is_spread:
        strike_2 = col2.number_input("Strike 2", value=float(st.session_state.draft_trade["strike_2"]))
    
    premium = col1.number_input("Premium (per share)", value=float(st.session_state.draft_trade["premium"]))
    iv_input = col2.number_input("Implied Vol (decimal)", value=float(st.session_state.draft_trade["iv"]))
    exp_date = st.date_input("Expiration", value=st.session_state.draft_trade["expiration"])

    # Update session state
    st.session_state.draft_trade.update({
        "trade_type": t_type,
        "qty": qty,
        "strike": strike,
        "strike_2": strike_2,
        "premium": premium,
        "iv": iv_input,
        "expiration": exp_date
    })
    update_draft_time()

# --- Create Simulation Trade Object ---
if ticker:
    try:
        draft_trade = Trade(
            trade_type=t_type,
            ticker=ticker,
            qty=qty,
            strike=strike if strike > 0 else None,
            strike_2=strike_2 if strike_2 > 0 else None,
            premium=premium,
            expiration=exp_date.strftime("%Y-%m-%d"),
            underlying_price=st.session_state.draft_trade.get("underlying_price"),
            iv=iv_input
        )
        
        with col_met:
            # 1. Top Level Metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Expected Value", f"${draft_trade.expected_profit:,.2f}")
            m2.metric("Prob. of Profit", f"{draft_trade.pop*100:.1f}%")
            m3.metric("Max Gain", f"${draft_trade.max_gain:,.2f}")
            m4.metric("Max Loss", f"${draft_trade.max_loss:,.2f}")

            m5, m6, m7, m8 = st.columns(4)
            m5.metric("VaR (95%)", f"${draft_trade.var_95:,.2f}")
            m6.metric("CVaR (95%)", f"${draft_trade.cvar_95:,.2f}")
            m7.metric("Kelly Criterion", f"{draft_trade.kelly_criterion*100:.1f}%")
            
            # Custom delta calculation based on utils.py logic
            beta = api.get_stock_beta(ticker)
            raw_delta = 0.0
            t_low = t_type.lower()
            if t_low == "shares": raw_delta = qty 
            elif t_low in ["csp", "short_put"]: raw_delta = 0.50 * 100 * qty 
            elif t_low in ["cc", "short_call"]: raw_delta = -0.50 * 100 * qty 
            elif t_low == "pcs": raw_delta = 0.25 * 100 * qty 
            elif t_low == "ccs": raw_delta = -0.25 * 100 * qty 
            elif t_low == "long_call" or t_low == "cds": raw_delta = 0.40 * 100 * qty 
            elif t_low == "long_put" or t_low == "pds": raw_delta = -0.40 * 100 * qty 
            
            trade_weighted_delta = raw_delta * beta
            m8.metric("Beta-W. Delta", f"{trade_weighted_delta:.2f}")

            if selected_p:
                if st.button("Execute & Save to Portfolio", width='stretch'):
                    db.store_trade(user_id, draft_trade, selected_p)
                    st.success(f"Successfully added {ticker} to {selected_p}!")
                    time.sleep(1)
                    st.switch_page("Dashboard.py")

            st.divider()

            # 2. Visualizations
            st.subheader("Payoff Diagram & Probability Analysis")
            
            S0 = draft_trade.underlying_price
            price_range = np.linspace(S0 * 0.7, S0 * 1.3, 200)
            payoffs = draft_trade.get_payoff_at_prices(price_range)
            
            # Probability Density (Lognormal)
            iv = draft_trade.iv
            T = draft_trade.dte / 365.0 if draft_trade.trade_type != "shares" else 1.0
            sigma_t = iv * np.sqrt(T)
            
            # mu = ln(S0) - 0.5 * sigma^2 * T
            mu = np.log(S0) - 0.5 * (iv**2) * T
            dist = stats.lognorm(s=sigma_t, scale=np.exp(mu))
            densities = dist.pdf(price_range)
            
            fig = objects.Figure()
            
            # Payoff Line
            fig.add_trace(objects.Scatter(
                x=price_range, y=payoffs,
                name="Payoff at Expiration",
                line=dict(color="#0971B2", width=3)
            ))
            
            # Probability Density Overlay (Secondary Y)
            fig.add_trace(objects.Scatter(
                x=price_range, y=densities,
                name="Price Probability",
                fill='tozeroy',
                yaxis="y2",
                line=dict(color="rgba(0, 204, 150, 0.3)", width=0),
                fillcolor="rgba(0, 204, 150, 0.2)"
            ))
            
            fig.update_layout(
                template="plotly_dark",
                xaxis_title="Underlying Price ($)",
                yaxis_title="P&L ($)",
                yaxis2=dict(
                    title="Probability Density",
                    overlaying="y",
                    side="right",
                    showgrid=False
                ),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                hovermode="x unified"
            )
            
            # Zero Line
            fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)
            # Current Price Line
            fig.add_vline(x=S0, line_dash="dot", line_color="yellow", annotation_text="Current Price")
            
            st.plotly_chart(fig, width='stretch')

            # 3. Portfolio Impact Analysis
            if selected_p:
                st.divider()
                st.subheader(f"Impact on Portfolio: {selected_p}")
                
                current_trades = db.get_trades(user_id, selected_p)
                
                # --- Sector Impact ---
                st.write("**Sector Exposure Shift**")
                
                sectors = {}
                for t in current_trades:
                    sectors[t.sector] = sectors.get(t.sector, 0) + t.max_loss
                
                total_exp = sum(sectors.values())
                new_trade_exp = draft_trade.max_loss
                new_sector = draft_trade.sector
                
                sector_data = []
                all_sectors = set(list(sectors.keys()) + [new_sector])
                for s in all_sectors:
                    curr_val = sectors.get(s, 0)
                    curr_pct = (curr_val / total_exp * 100) if total_exp > 0 else 0
                    
                    sim_val = curr_val + (new_trade_exp if s == new_sector else 0)
                    sim_pct = (sim_val / (total_exp + new_trade_exp) * 100) if (total_exp + new_trade_exp) > 0 else 0
                    
                    sector_data.append({
                        "Sector": s,
                        "Current (%)": curr_pct,
                        "Simulated (%)": sim_pct,
                        "Change": sim_pct - curr_pct
                    })
                
                import pandas as pd
                st.table(pd.DataFrame(sector_data).set_index("Sector"))
                
                # --- Metrics Impact ---
                i_col1, i_col2, i_col3 = st.columns(3)
                
                # Portfolio Delta
                curr_delta = utils.get_portfolio_beta_delta(user_id, selected_p)
                i_col1.metric("Portfolio Delta", f"{curr_delta:.2f}", f"{trade_weighted_delta:+.2f}")
                
                # Portfolio HHI
                curr_hhi = utils.get_hhi(user_id, selected_p)
                # Simulated HHI is harder because we need the list of all tickers and their exposures
                ticker_exposures = {}
                for t in current_trades:
                    ticker_exposures[t.ticker] = ticker_exposures.get(t.ticker, 0) + t.max_loss
                ticker_exposures[ticker] = ticker_exposures.get(ticker, 0) + new_trade_exp
                
                new_total_exp = sum(ticker_exposures.values())
                new_hhi = sum([(v/new_total_exp)**2 for v in ticker_exposures.values()]) if new_total_exp > 0 else 0
                
                i_col2.metric("Portfolio HHI", f"{curr_hhi:.2f}", f"{new_hhi - curr_hhi:+.2f}")
                
                # Portfolio Max Loss
                curr_exp = utils.get_gross_exposure(user_id, selected_p)
                i_col3.metric("Gross Exposure", f"${curr_exp:,.2f}", f"${new_trade_exp:,.2f}")
            else:
                st.info("Select a portfolio on the Dashboard to see impact analysis.")

    except Exception as e:
        st.error(f"Error simulating trade: {e}")
        import traceback
        st.write(traceback.format_exc())
else:
    st.info("Enter a ticker to begin analysis.")
