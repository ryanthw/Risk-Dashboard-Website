import streamlit as st
import database_sq as db
import utils
from trade import Trade
from datetime import datetime
import time

# --- Page Config ---
st.set_page_config(page_title="Options Risk Dashboard", layout="wide")

# --- CSS Injections --- #
st.markdown("""
    <style>
    /* Metric styling */
    [data-testid="stMetricLabel"] { font-size: 0.8rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
    [data-testid="stMetric"] { padding: 0px !important; }

    /* Target by Aria-Label (Matches the exact text inside st.button) */
    
    /* Update Button */
    button[aria-label="Update Trade"] {
        background-color: #0971B2 !important;
        color: white !important;
        border: none !important;
    }

    /* Delete Button */
    button[aria-label="Delete Trade"] {
        background-color: #8b0000 !important;
        color: white !important;
        border: none !important;
    }

    /* Hover States */
    button[aria-label="Update Trade"]:hover {
        background-color: #0a85d4 !important;
    }
    
    button[aria-label="Delete Trade"]:hover {
        background-color: #a30000 !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- Initialize DB ---
db.init_db()

# --- Sidebar: Portfolio Management ---
with st.sidebar:
    st.title("Portfolio Manager")
    
    # --- 1. SWITCH PORTFOLIO ---
    ports = db.get_portfolios()

    # Safety: Ensure active_portfolio is valid and exists in current ports
    if "active_portfolio" not in st.session_state or st.session_state.active_portfolio not in ports:
        st.session_state.active_portfolio = ports[0] if ports else None

    # Calculate index safely
    current_index = 0
    if st.session_state.active_portfolio in ports:
        current_index = ports.index(st.session_state.active_portfolio)

    selected_p = st.selectbox(
        "Select Active Portfolio", 
        ports, 
        index=current_index,
        key="port_selector"
    )
    st.session_state.active_portfolio = selected_p

    st.divider()

    # 2. PORTFOLIO ACTIONS (Create/Delete)
    with st.expander("Manage Portfolios"):
        tab1, tab2 = st.tabs(["Add", "Delete"])
        
        with tab1:
            # Use a unique key for the text input
            new_port_name = st.text_input("New Portfolio Name", key="unique_port_input_key")
            
            if st.button("Confirm Create"):
                if new_port_name:
                    existing_ports = db.get_portfolios()
                    if new_port_name in existing_ports:
                        st.error("That name is already in the database.")
                    else:
                        db.build_portfolio(new_port_name)
                        # Force the app to recognize the new portfolio immediately
                        st.session_state.active_portfolio = new_port_name
                        st.success(f"Successfully created '{new_port_name}'")
                        st.rerun()
        
        with tab2:
            if ports:
                port_to_delete = st.selectbox("Portfolio to Remove", ports)
                # Double-check confirmation
                confirm = st.checkbox(f"Confirm deletion of {port_to_delete}")
                if st.button("Permanently Delete") and confirm:
                    db.delete_portfolio(port_to_delete)
                    # Reset session state if we deleted the current one
                    if port_to_delete == st.session_state.active_portfolio:
                        st.session_state.active_portfolio = ports[0] if len(ports) > 1 else None
                    st.rerun()
            else:
                st.write("No portfolios to delete.")
    
    st.divider()

    # Add New Trade Form
    with st.expander("Add New Trade"):
        with st.form("add_trade"):
            t_type = st.selectbox("Type", ["shares", "csp", "cc", "short_call", "short_put", "long_call", "long_put"])
            ticker = st.text_input("Ticker")
            qty = st.number_input("Quantity", min_value=1, value=1)
            strike = st.number_input("Strike", value=0.0)
            prem = st.number_input("Premium", value=0.0)
            exp_date = st.date_input("Expiration", value=datetime.now())
            iv = st.number_input("IV (decimal)", value=0.20)
            
            if st.form_submit_button("Save Trade"):
                new_trade = Trade(
                    trade_type=t_type,
                    ticker=ticker,
                    qty=qty,
                    strike=strike if strike > 0 else None,
                    premium=prem,
                    expiration=exp_date.strftime("%Y-%m-%d"),
                    underlying_price=None, # Will fetch via API in Trade class
                    iv=iv
                )
                db.store_trade(new_trade, selected_p)
                st.success(f"Added {ticker}")
                st.rerun()

    st.divider()

    # Update Cash Balance
    with st.expander("Update Cash Balance"):
        current_cash = db.get_cash(selected_p)
        st.write(f"Current: ${current_cash:,.2f}")
        
        with st.form("cash_form", clear_on_submit=True):
            new_cash = st.number_input("New Cash Amount", min_value=0.0, step=100.0, value=current_cash)
            if st.form_submit_button("Update Balance"):
                db.update_cash(new_cash, selected_p)
                st.success("Cash Updated!")
                st.rerun()  # Refreshes the dashboard to show new metrics

    st.divider()

    # --- MANUAL REFRESH BUTTON ---
    if st.button("Refresh Market Data", use_container_width=True):
        with st.status("Fetching latest prices...", expanded=True) as status:
            st.write("Connecting to Finnhub...")
            utils.update_underlyings(selected_p) # Your existing logic
            st.write("Recalculating Monte Carlo simulations...")
            status.update(label="Refresh Complete!", state="complete", expanded=False)
        
        # Display a success message and rerun to show new data
        st.success("Portfolio Updated!")
        time.sleep(1) # Brief pause so you can see the success message
        st.rerun()

# --- MAIN DASHBOARD ---
st.header(f"Portfolio: {selected_p}")

# 1. Top Level Metrics (The Big 5)
col1, col2, col3, col4, col5 = st.columns(5)
port_val = db.get_portfolio_val(selected_p)
trades = db.get_trades(selected_p)
ers = [t.expected_profit for t in trades]

with col1:
    st.metric("Total Value", f"${port_val:,.2f}")
with col2:
    st.metric("Gross Exposure", f"${utils.get_gross_exposure(selected_p):,.2f}")
with col3:
    st.metric("Sortino Ratio", f"{utils.get_sortino_ratio(selected_p):.3f}")
with col4:
    st.metric("HHI (Conc.)", f"{utils.get_hhi(selected_p):.2f}")
with col5:
    st.metric("Open Trades:", f"{len(trades)}")

st.divider()

# 2. Main Body: Split into Risk Stats (Left) and Trade List (Right)
main_left, main_right = st.columns([0.6, 0.4]) # 60% left, 40% right

with main_left:
    st.subheader("Risk Analysis")
    
    # Internal Grid for Risk Metrics (2 columns)
    r_col1, r_col2 = st.columns(2)
    
    # Benchmarks (SPY data)
    spy_ret_lt = 7.5
    spy_ret_st = ((1 + .075) ** (1 / 26) - 1) * 100 

    with r_col1:
        st.write("**Exposure & Leverage**")
        st.info(f"Percent Exposure: {utils.get_percent_exposure(selected_p):.2f}%")
        st.info(f"Leverage Ratio: {utils.get_leverage_ratio(selected_p):.2f}x")
        st.info(f"Cash to Pos Ratio: {utils.get_cash_to_pos_ratio(selected_p):.2f}")
        st.info(f"Highest Pos: {utils.get_highest_pos_percent(selected_p):.2f}%")
        
        st.write("**Performance Multipliers**")
        er_ann = utils.get_er_ann(selected_p)
        er_pct = utils.get_er_percent(ers, selected_p)
        st.success(f"LT Alpha: {er_ann / spy_ret_lt:.2f}x")
        st.success(f"ST Alpha: {er_pct / spy_ret_st:.2f}x")

    with r_col2:
        st.write("**Returns & Profitability**")
        st.info(f"Expected Returns: ${utils.get_expected_returns(ers):,.2f}")
        st.info(f"ERP: {er_pct:.2f}%")
        st.info(f"ERPA: {er_ann:.2f}%")
        st.info(f"Max Gain: ${utils.get_max_profit(selected_p):,.2f}")
        
        st.write("**Efficiency**")
        st.info(f"Risk/Reward Ratio: {utils.get_risk_reward_ratio(selected_p):.2f}")
        st.info(f"Cash Percent: {utils.get_cash_percent(selected_p):.2f}%")

with main_right:
    st.subheader("Open Trades")

    # --- Update Popup Form --- #
    if "editing_trade_id" in st.session_state and st.session_state.editing_trade_id:
        edit_id = st.session_state.editing_trade_id
        t_to_edit = db.get_trade_by_id(edit_id, selected_p)
        
        if t_to_edit:
            with st.container(border=True):
                st.write(f"### Update {t_to_edit.ticker}")
                with st.form("update_trade_form"):
                    col_a, col_b = st.columns(2)
                    new_iv = col_a.number_input("Implied Vol (decimal)", value=float(t_to_edit.iv))
                    new_qty = col_b.number_input("Quantity", value=int(t_to_edit.qty), min_value=1)
                    new_prem = col_a.number_input("Premium", value=float(t_to_edit.premium))
                    new_strike = col_b.number_input("Strike", value=float(t_to_edit.strike) if t_to_edit.strike else 0.0)
                    
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.form_submit_button("Save Changes"):
                        # Update the object
                        t_to_edit.iv = new_iv
                        t_to_edit.qty = new_qty
                        t_to_edit.premium = new_prem
                        t_to_edit.strike = new_strike if new_strike > 0 else None
                        
                        # Refresh P&L math and Save
                        t_to_edit.refresh_pnl()
                        db.store_trade(t_to_edit, selected_p)
                        
                        st.session_state.editing_trade_id = None
                        st.success("Trade Updated!")
                        st.rerun()
                        
                    if c_btn2.form_submit_button("Cancel"):
                        st.session_state.editing_trade_id = None
                        st.rerun()

    # --- Trade Card Layout --- #
    if not trades:
        st.info("No open trades.")
    else:
        # We can make this a scrollable container to mimic your scrollable frame
        with st.container(height=600): # Set a fixed height for scrolling
            for t in trades:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    c1.markdown(f"**{t.ticker}** ({t.trade_type.upper()})")
                    c1.caption(f"Exp: {t.expiration.date()}")
                    c2.metric("Value", f"{t.value:.2f}")
                    c3.metric("E[P]", f"{t.expected_profit:.2f}")
                    c4.metric("POP", f"{t.pop*100:.2f}%")
                    
                    if st.button("Update Trade", key=f"upd_{t.trade_id}", use_container_width=True):
                        st.session_state.editing_trade_id = t.trade_id
                        st.rerun()
                
                    if st.button("Delete Trade", type="primary", key=f"del_{t.trade_id}", use_container_width=True):
                        db.delete_trade(t.trade_id)
                        st.rerun()