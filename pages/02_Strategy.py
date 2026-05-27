import streamlit as st
import database_sq as db
import utils
import pandas as pd
import plotly.express as px
import yfinance as yf
import numpy as np
import plotly.figure_factory as ff

st.set_page_config(page_title="PM Strategy", layout="wide")

# --- Auth Check ---
if "user" not in st.session_state:
    st.warning("Please login on the Home page first.")
    st.stop()

user_id = st.session_state.user.id

# 1. Verification
if "active_portfolio" not in st.session_state or not st.session_state.active_portfolio:
    st.warning("👈 Please select a portfolio on the Home page first.")
    st.stop()

selected_p = st.session_state.active_portfolio
st.title(f"PM Strategy & Allocation: {selected_p}")

# 2. Data Loading & Pre-processing
trades = db.get_trades(user_id, selected_p)
port_val = db.get_portfolio_val(user_id, selected_p)

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

# --- ADVANCED MATH ---
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
beta_delta = utils.get_portfolio_beta_delta(user_id, selected_p)
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
TARGETS = {
    "Dividend Engine": 0.125, 
    "S&P 500 Core": 0.125,
    "Income Driver (Wheel)": 0.60, 
    "Credit Spreads": 0.10, 
    "Cash/Hedges": 0.05
}
core_engine_tickers = ["SCHD", "VIG", "ORC", "MAIN", "AGNC", "ARCC"]

engine_risk = df[(df["Type"] == "shares") & (df["Ticker"].isin(core_engine_tickers))]["Max Loss"].sum()
spy_risk = df[(df["Type"] == "shares") & (df["Ticker"] == "SPY")]["Max Loss"].sum()

# Income Driver: Non-core shares (excluding SPY and Dividend list) + Short Options (excluding Spreads)
driver_risk = df[
    (df["Type"].isin(["csp", "cc", "short_put", "short_call"])) | 
    ((df["Type"] == "shares") & (~df["Ticker"].isin(core_engine_tickers)) & (df["Ticker"] != "SPY"))
]["Max Loss"].sum()

spread_risk = df[df["Type"].isin(["pcs", "ccs", "cds", "pds"])]["Max Loss"].sum()
actual_cash = utils.get_undeployed_cash(user_id, selected_p)

def render_fulfillment(label, actual_val, target_pct):
    actual_pct = actual_val / port_val if port_val > 0 else 0
    progress = min(actual_pct / target_pct, 1.0)
    c1, c2, c3 = st.columns([1, 2, 1])
    c1.write(f"**{label}**")
    c2.progress(progress)
    c3.metric("Actual", f"{actual_pct*100:.1f}%", f"{(actual_pct-target_pct)*100:.1f}% vs Target")

render_fulfillment("Dividend Engine", engine_risk, TARGETS["Dividend Engine"])
render_fulfillment("S&P 500 Core", spy_risk, TARGETS["S&P 500 Core"])
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

# --- SECTION 5: OPPORTUNITY SCANNER ---
st.divider()
st.subheader("🔍 Income Driver: Opportunity Scanner")
st.write("Scan a custom watchlist for high IV, low cost, and diversification opportunities (Wheel Strategy).")

with st.expander("Configure Scanner", expanded=True):
    col_in1, col_in2 = st.columns([2, 1])
    
    default_watchlist = "AMD, F, BAC, KO, TGT, XOM, PFE, INTC, PLTR, SOFI, CCL, AAL, VALE, RDW, CLSK"
    watchlist_input = col_in1.text_area("Watchlist (Comma Separated)", value=default_watchlist, help="Enter tickers you are willing to own.")
    
    max_price = col_in2.slider("Max Share Price ($)", 10, 500, 100)
    target_dte = 45

    if st.button("Run Opportunity Scan", use_container_width=True):
        tickers_to_scan = [t.strip().upper() for t in watchlist_input.split(",") if t.strip()]
        
        if not tickers_to_scan:
            st.error("Please enter at least one ticker.")
        else:
            with st.status("Scanning market data...", expanded=True) as status:
                results = []
                
                # Calculate current sector exposure for diversification scoring
                sector_exposure = df.groupby("Sector")["Max Loss"].sum()
                total_max_loss = sector_exposure.sum()
                sector_weights = (sector_exposure / total_max_loss).to_dict() if total_max_loss > 0 else {}
                
                import api_interactions as api_int
                from datetime import datetime, timedelta

                for ticker in tickers_to_scan:
                    try:
                        status.write(f"Analyzing {ticker}...")
                        price = api_int.get_price(ticker)
                        
                        if price > max_price or price <= 0:
                            continue
                            
                        iv = api_int.get_historical_volatility(ticker)
                        sector = api_int.get_company_sector(ticker)
                        
                        # Diversification Scoring: Reward sectors you DON'T have much of
                        current_weight = sector_weights.get(sector, 0.0)
                        div_score = 1.0 - current_weight
                        
                        # Ranking Score: IV * Diversification
                        rank_score = iv * div_score
                        
                        # Suggest Strike (Approx 0.30 Delta)
                        # Formula: Strike = Price * (1 - 0.5 * IV * sqrt(DTE/365))
                        std_dev_move = iv * np.sqrt(target_dte / 365.0)
                        suggested_strike = price * (1 - 0.5 * std_dev_move)
                        
                        # Round to nearest 0.5 or 1.0 for realism
                        if suggested_strike > 20:
                            suggested_strike = round(suggested_strike)
                        else:
                            suggested_strike = round(suggested_strike * 2) / 2
                            
                        exp_date = (datetime.now() + timedelta(days=target_dte)).strftime("%Y-%m-%d")
                        
                        results.append({
                            "Ticker": ticker,
                            "Sector": sector,
                            "Price": f"${price:.2f}",
                            "IV (30d)": f"{iv*100:.1f}%",
                            "Suggested Strike": f"${suggested_strike}",
                            "Suggested Exp": exp_date,
                            "Div. Rating": "Good" if current_weight < 0.05 else ("Neutral" if current_weight < 0.15 else "Poor"),
                            "_score": rank_score
                        })
                    except Exception as e:
                        status.write(f"Error scanning {ticker}: {e}")
                        continue
                
                if results:
                    # Sort by rank_score descending
                    results_df = pd.DataFrame(results).sort_values("_score", ascending=False).drop(columns=["_score"])
                    
                    status.update(label="Scan Complete!", state="complete", expanded=False)
                    st.success(f"Found {len(results_df)} opportunities matching your criteria.")
                    
                    st.dataframe(
                        results_df,
                        use_container_width=True,
                        hide_index=True
                    )
                    st.info("💡 **Tip:** 'Good' Diversification Rating means the ticker is in a sector where you currently have low exposure (<5%).")
                else:
                    status.update(label="No matches found.", state="error", expanded=True)
                    st.warning("No tickers from your watchlist met the price criteria or had valid data.")

