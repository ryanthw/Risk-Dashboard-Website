import pickle
from supabase import create_client
import streamlit as st
from datetime import datetime

# Initialize Supabase client
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

def init_db():
    """
    Note: In Supabase, you should run the SQL in their 'SQL Editor' dashboard:
    
    CREATE TABLE IF NOT EXISTS portfolios (
        name TEXT PRIMARY KEY,
        cash REAL DEFAULT 0.0
    );

    CREATE TABLE IF NOT EXISTS trades (
        trade_id TEXT PRIMARY KEY,
        portfolio_name TEXT REFERENCES portfolios(name) ON DELETE CASCADE,
        data TEXT
    );
    """
    pass # Table creation is handled via Supabase Dashboard UI

@st.cache_data(ttl=600)
def get_portfolios():
    response = supabase.table("portfolios").select("name").execute()
    return [row['name'] for row in response.data]

def build_portfolio(name):
    name = name.strip()
    # Supabase returns a 'data' and an 'error' property
    response = supabase.table("portfolios").insert({"name": name, "cash": 0.0}).execute()
    
    # If Supabase has an error attribute (like duplicate primary key)
    if hasattr(response, 'error') and response.error:
        raise ValueError(f"Could not create portfolio: {response.error.message}")
    
    st.cache_data.clear()

def delete_portfolio(p_name):
    # Foreign Key Cascade should handle trades if set up in SQL Editor,
    # but we will be explicit to match your old logic.
    supabase.table("trades").delete().eq("portfolio_name", p_name).execute()
    supabase.table("portfolios").delete().eq("name", p_name).execute()
    st.cache_data.clear()

@st.cache_data(ttl=600)
def get_cash(p_name):
    response = supabase.table("portfolios").select("cash").eq("name", p_name).execute()
    if response.data:
        return float(response.data[0]['cash'])
    return 0.0

def update_cash(val, p_name):
    supabase.table("portfolios").update({"cash": float(val)}).eq("name", p_name).execute()
    st.cache_data.clear()

def store_trade(trade, p_name):
    # 1. Convert object to bytes, then to a clean hex string
    trade_data_hex = pickle.dumps(trade).hex()
    
    payload = {
        "trade_id": trade.trade_id,
        "portfolio_name": p_name,
        "data": trade_data_hex  # This is now a plain string
    }
    supabase.table("trades").upsert(payload).execute()
    st.cache_data.clear()

def get_trade_by_id(trade_id, p_name):
    response = supabase.table("trades").select("data").eq("trade_id", trade_id).eq("portfolio_name", p_name).execute()
    if response.data:
        hex_data = response.data[0]['data']
        try:
            if isinstance(hex_data, str):
                if hex_data.startswith('\\x'):
                    hex_data = hex_data[2:]
                return pickle.loads(bytes.fromhex(hex_data))
            else:
                return pickle.loads(bytes(hex_data))
        except Exception as e:
            print(f"Error unpickling specific trade: {e}")
    return None

@st.cache_data(ttl=600)
def get_trades(p_name):
    response = supabase.table("trades").select("data").eq("portfolio_name", p_name).execute()
    
    trades_list = []
    for row in response.data:
        hex_data = row['data']
        
        try:
            # Since we changed the column to TEXT, Supabase returns a clean string.
            # We just need to strip any Postgres prefix if it exists.
            if isinstance(hex_data, str):
                if hex_data.startswith('\\x'):
                    hex_data = hex_data[2:]
                
                # Convert hex string back to bytes
                actual_binary = bytes.fromhex(hex_data)
                
                # Unpickle
                trades_list.append(pickle.loads(actual_binary))
        except Exception as e:
            print(f"Error decoding trade row: {e}")
            continue
            
    return trades_list

def delete_trade(trade_id):
    supabase.table("trades").delete().eq("trade_id", trade_id).execute()
    st.cache_data.clear()

def get_portfolio_val(p_name):
    val = get_cash(p_name)
    trades = get_trades(p_name)
    # Update this set to include your new credit types
    credit_trades = {"csp", "cc", "short_put", "short_call", "pcs", "ccs"}
    for trade in trades:
        if trade.trade_type not in credit_trades:
            val += trade.value
    return val

# Historical Data Storage
def archive_trade(p_name, trade_obj, realized_pnl):
    """
    Archives a trade. 
    Fixes JSON serialization by converting datetime objects to strings.
    """
    try:
        # Safeguard for PnL
        if realized_pnl is None:
            realized_pnl = 0.0
            
        # --- FIX: Date Serialization ---
        # If entry_date is a datetime object, convert to ISO string. 
        # If it's already a string or None, keep as is.
        entry_dt = getattr(trade_obj, 'opened', None)
        if isinstance(entry_dt, datetime):
            entry_dt = entry_dt.isoformat()
            
        # We also want to record exactly when the trade was closed
        exit_dt = datetime.now().isoformat()

        data = {
            "portfolio_name": p_name,
            "ticker": trade_obj.ticker,
            "trade_type": trade_obj.trade_type,
            "entry_date": entry_dt,
            "exit_date": exit_dt,
            "realized_pnl": float(realized_pnl),
            "iv_at_close": getattr(trade_obj, 'iv', 0.0),
            "max_loss": trade_obj.max_loss,
            "final_value": getattr(trade_obj, 'value', 0.0)
        }
        
        supabase.table("history_trades").insert(data).execute()
        return True
    except Exception as e:
        # This will now catch and print the specific error if one remains
        print(f"Error archiving trade: {e}")
        return False

def record_portfolio_snapshot(p_name, metrics):
    """
    Records a high-level health snapshot of the portfolio.
    metrics should contain: net_liquidity, weighted_delta, expected_profit_total, erpa
    """
    try:
        metrics["portfolio_name"] = p_name
        supabase.table("history_snapshots").insert(metrics).execute()
        return True
    except Exception as e:
        print(f"Error recording snapshot: {e}")
        return False
    
def check_snapshot_exists(p_name, date_str):
    """
    Checks if a snapshot for the given portfolio and date (YYYY-MM-DD) exists.
    """
    res = supabase.table("history_snapshots")\
        .select("id")\
        .eq("portfolio_name", p_name)\
        .gte("timestamp", f"{date_str}T00:00:00")\
        .lte("timestamp", f"{date_str}T23:59:59")\
        .execute()
    return len(res.data) > 0