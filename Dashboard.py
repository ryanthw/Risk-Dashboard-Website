import streamlit as st
import database_sq as db
import utils
from trade import Trade
from datetime import datetime
import time

# --- Auth --- #
def auth_form():
    st.title("Risk Dashboard")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            if submit:
                try:
                    res = db.supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = res.user
                    st.success("Logged in!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {str(e)}")
                    
    with tab2:
        with st.form("signup_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submit = st.form_submit_button("Create Account")
            if submit:
                if password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    try:
                        res = db.supabase.auth.sign_up({"email": email, "password": password})
                        st.success("Account created! Please check your email for confirmation (if enabled) and then login.")
                    except Exception as e:
                        st.error(f"Signup failed: {str(e)}")

def check_auth():
    if "user" not in st.session_state:
        auth_form()
        st.stop()

check_auth()
user_id = st.session_state.user.id

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

# --- Sidebar: Portfolio Management ---
with st.sidebar:
    st.title("Portfolio Manager")
    st.write(f"Logged in as: {st.session_state.user.email}")
    if st.button("Logout"):
        db.supabase.auth.sign_out()
        del st.session_state.user
        st.rerun()

    # --- 1. SWITCH PORTFOLIO ---
    ports = db.get_portfolios(user_id)

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
            new_port_name = st.text_input("New Portfolio Name", key="unique_port_input_key")
            
            if st.button("Confirm Create"):
                if new_port_name:
                    existing_ports = db.get_portfolios(user_id)
                    if new_port_name in existing_ports:
                        st.error("That name is already in the database.")
                    else:
                        db.build_portfolio(user_id, new_port_name)
                        st.session_state.active_portfolio = new_port_name
                        st.success(f"Successfully created '{new_port_name}'")
                        st.rerun()
        
        with tab2:
            if ports:
                port_to_delete = st.selectbox("Portfolio to Remove", ports)
                confirm = st.checkbox(f"Confirm deletion of {port_to_delete}")
                if st.button("Permanently Delete") and confirm:
                    db.delete_portfolio(user_id, port_to_delete)
                    if port_to_delete == st.session_state.active_portfolio:
                        st.session_state.active_portfolio = ports[0] if len(ports) > 1 else None
                    st.rerun()
            else:
                st.write("No portfolios to delete.")
    
    st.divider()

    # --- Updated Sidebar "Add New Trade" logic ---
    with st.expander("Add New Trade"):
        t_type = st.selectbox("Type", [
            "shares", "csp", "cc", "short_call", "short_put", 
            "long_call", "long_put", "pcs", "ccs", "cds", "pds"
        ])
        
        with st.form("add_trade_form", clear_on_submit=True):
            ticker = st.text_input("Ticker")
            qty = st.number_input("Quantity", min_value=1, value=1)
            
            col1, col2 = st.columns(2)
            strike = col1.number_input("Strike (Short)", value=0.0)
            
            strike_2 = 0.0
            if t_type in ["pcs", "ccs", "cds", "pds"]:
                strike_2 = col2.number_input("Strike 2 (Long)", value=0.0)
            else:
                col2.write("") 
                
            prem = col1.number_input("Premium", value=0.0)
            iv = col2.number_input("IV", value=0.20)
            exp_date = st.date_input("Expiration", value=datetime.now())
            
            if st.form_submit_button("Save Trade"):
                if t_type in ["pcs", "ccs", "cds", "pds"] and strike == strike_2:
                    st.error("Strikes must be different for a spread.")
                else:
                    new_trade = Trade(
                        trade_type=t_type,
                        ticker=ticker,
                        qty=qty,
                        strike=strike if strike > 0 else None,
                        strike_2=strike_2 if strike_2 > 0 else None,
                        premium=prem,
                        expiration=exp_date.strftime("%Y-%m-%d"),
                        underlying_price=None, 
                        iv=iv
                    )
                    db.store_trade(user_id, new_trade, selected_p)
                    st.success(f"Added {ticker}")
                    st.rerun()

    st.divider()

    # Update Cash Balance
    with st.expander("Update Cash Balance"):
        current_cash = db.get_cash(user_id, selected_p)
        st.write(f"Current: ${current_cash:,.2f}")
        
        with st.form("cash_form", clear_on_submit=True):
            new_cash = st.number_input("New Cash Amount", min_value=0.0, step=100.0, value=float(current_cash))
            if st.form_submit_button("Update Balance"):
                db.update_cash(user_id, new_cash, selected_p)
                st.success("Cash Updated!")
                st.rerun() 

    st.divider()

    # --- MANUAL REFRESH BUTTON ---
    if st.button("Refresh Market Data", use_container_width=True):
        with st.status("Fetching latest prices...", expanded=True) as status:
            st.cache_data.clear()
            st.write("Connecting to Finnhub...")
            utils.update_underlyings(user_id, selected_p) 
            st.write("Recalculating Monte Carlo simulations...")
            utils.capture_and_save_snapshot(user_id, selected_p)
            st.write("Saving Portfolio Snapshot")
            status.update(label="Refresh Complete!", state="complete", expanded=False)
        
        st.success("Portfolio Updated, Snapshot Logged!")
        time.sleep(1) 
        st.rerun()

# --- MAIN DASHBOARD ---
if selected_p:
    st.header(f"Portfolio: {selected_p}")

    # 1. Top Level Metrics (The Big 5)
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    port_val = db.get_portfolio_val(user_id, selected_p)
    trades = db.get_trades(user_id, selected_p)
    ers = [t.expected_profit for t in trades if t.trade_type != "shares"]

    with col1:
        st.metric("Total Value", f"${port_val:,.2f}")
    with col2:
        st.metric("Gross Exposure", f"${utils.get_gross_exposure(user_id, selected_p):,.2f}")
    with col3:
        st.metric("Net Liquidity", f"{utils.get_net_liquidity(user_id, selected_p):.2f}")
    with col4:
        st.metric("Sortino Ratio", f"{utils.get_sortino_ratio(user_id, selected_p):.3f}")
    with col5:
        st.metric("HHI (Conc.)", f"{utils.get_hhi(user_id, selected_p):.2f}")
    with col6:
        st.metric("Open Trades:", f"{len(trades)}")

    st.divider()

    # 2. Main Body: Split into Risk Stats (Left) and Trade List (Right)
    main_left, main_right = st.columns([0.6, 0.4]) 

    with main_left:
        st.subheader("Risk Analysis")
        
        r_col1, r_col2 = st.columns(2)
        
        spy_ret_lt = 7.5
        spy_ret_st = ((1 + .075) ** (1 / 26) - 1) * 100 

        with r_col1:
            st.write("**Exposure & Leverage**")
            st.info(f"Percent Exposure: {utils.get_percent_exposure(user_id, selected_p):.2f}%")
            st.info(f"Leverage Ratio: {utils.get_leverage_ratio(user_id, selected_p):.2f}x")
            st.info(f"Cash to Pos Ratio: {utils.get_cash_to_pos_ratio(user_id, selected_p):.2f}")
            st.info(f"Highest Pos: {utils.get_highest_pos_percent(user_id, selected_p):.2f}%")
            
            st.write("**Performance Multipliers**")
            er_ann = utils.get_er_ann(user_id, selected_p) * 100
            er_pct = utils.get_er_percent(user_id, ers, selected_p)
            st.success(f"LT Alpha: {er_ann / spy_ret_lt:.2f}x")
            st.success(f"ST Alpha: {er_pct / spy_ret_st:.2f}x")

        with r_col2:
            st.write("**Returns & Profitability**")
            st.info(f"Expected Returns: ${utils.get_expected_returns(ers):,.2f}")
            st.info(f"ERP: {er_pct:.2f}%")
            st.info(f"ERPA: {er_ann:.2f}%")
            st.info(f"Max Gain: ${utils.get_max_profit(user_id, selected_p):,.2f}")
            
            st.write("**Efficiency**")
            st.info(f"Risk/Reward Ratio: {utils.get_risk_reward_ratio(user_id, selected_p):.2f}")
            st.info(f"Cash Percent: {utils.get_cash_percent(user_id, selected_p):.2f}%")

    with main_right:
        st.subheader("Open Trades")

        if "editing_trade_id" in st.session_state and st.session_state.editing_trade_id:
            edit_id = st.session_state.editing_trade_id
            t_to_edit = db.get_trade_by_id(user_id, edit_id, selected_p)
            
            if t_to_edit:
                is_spread = t_to_edit.trade_type in ["pcs", "ccs", "cds", "pds"]
                
                with st.container(border=True):
                    st.write(f"### Update {t_to_edit.ticker}")
                    with st.form("update_trade_form"):
                        col_a, col_b = st.columns(2)
                        
                        new_iv = col_a.number_input("Implied Vol (decimal)", value=float(t_to_edit.iv))
                        new_prem = col_a.number_input("Premium", value=float(t_to_edit.premium))
                        
                        new_qty = col_b.number_input("Quantity", value=int(t_to_edit.qty), min_value=1)
                        new_strike = col_b.number_input("Strike 1 (Short/Main)", value=float(t_to_edit.strike) if t_to_edit.strike else 0.0)
                        
                        new_strike_2 = 0.0
                        if is_spread:
                            current_s2 = getattr(t_to_edit, 'strike_2', 0.0)
                            new_strike_2 = col_b.number_input("Strike 2 (Long/Protection)", value=float(current_s2) if current_s2 else 0.0)
                        
                        c_btn1, c_btn2 = st.columns(2)
                        
                        if c_btn1.form_submit_button("Save Changes"):
                            t_to_edit.iv = new_iv
                            t_to_edit.qty = new_qty
                            t_to_edit.premium = new_prem
                            t_to_edit.strike = new_strike if new_strike > 0 else None
                            
                            if is_spread:
                                t_to_edit.strike_2 = new_strike_2
                            
                            t_to_edit.refresh_pnl()
                            db.store_trade(user_id, t_to_edit, selected_p)
                            
                            st.session_state.editing_trade_id = None
                            st.success("Trade Updated!")
                            st.rerun()
                            
                        if c_btn2.form_submit_button("Cancel"):
                            st.session_state.editing_trade_id = None
                            st.rerun()

        if not trades:
            st.info("No open trades.")
        else:
            with st.container(height=600): 
                for t in trades:
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                        c1.markdown(f"**{t.ticker}** ({t.trade_type.upper()})")
                        c1.caption(f"Exp: {t.expiration.date()}")
                        c2.metric("Value", f"{t.value:.2f}")
                        c3.metric("E[P]", f"{t.expected_profit:.2f}")
                        c4.metric("POP", f"{t.pop*100:.2f}%")
                        
                        btn_col1, btn_col2 = st.columns(2)
                        
                        with btn_col1:
                            if st.button("Update Trade", key=f"upd_{t.trade_id}", use_container_width=True):
                                st.session_state.editing_trade_id = t.trade_id
                                st.rerun()
                    
                        with btn_col2:
                            with st.popover("Close", use_container_width=True):
                                st.write("### Close Position")
                                
                                st.write("**Archive to History**")
                                realized_pnl = st.number_input(
                                    "Final Realized P&L", 
                                    value=float(t.expected_profit),
                                    step=10.0,
                                    format="%.2f",
                                    key=f"pnl_in_{t.trade_id}"
                                )
                                
                                if st.button("Confirm & Archive", key=f"arch_btn_{t.trade_id}", use_container_width=True):
                                    final_val = realized_pnl if realized_pnl is not None else 0.0
                                    db.archive_trade(user_id, selected_p, t, final_val)
                                    db.delete_trade(user_id, t.trade_id)
                                    
                                    st.success(f"Archived {t.ticker} with ${final_val:.2f} P&L")
                                    time.sleep(0.5)
                                    st.rerun()
                                
                                st.divider()
                                
                                st.write("**Mistake / Remove**")
                                if st.button("Hard Delete (No History)", type="primary", key=f"hard_del_{t.trade_id}", use_container_width=True):
                                    db.delete_trade(user_id, t.trade_id)
                                    st.rerun()
else:
    st.info("Please create or select a portfolio in the sidebar to get started.")
