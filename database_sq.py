import pickle
from supabase import create_client
import streamlit as st

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
        data BYTEA
    );
    """
    pass # Table creation is handled via Supabase Dashboard UI

def get_portfolios():
    response = supabase.table("portfolios").select("name").execute()
    return [row['name'] for row in response.data]

def build_portfolio(name):
    name = name.strip()
    # Attempt to insert; if it fails due to PK violation, it raises an error
    response = supabase.table("portfolios").insert({"name": name, "cash": 0.0}).execute()
    # Check if the insert was successful (Supabase returns data on success)
    if not response.data:
        raise ValueError("Portfolio name already exists.")

def delete_portfolio(p_name):
    # Foreign Key Cascade should handle trades if set up in SQL Editor,
    # but we will be explicit to match your old logic.
    supabase.table("trades").delete().eq("portfolio_name", p_name).execute()
    supabase.table("portfolios").delete().eq("name", p_name).execute()

def get_cash(p_name):
    response = supabase.table("portfolios").select("cash").eq("name", p_name).execute()
    if response.data:
        return float(response.data[0]['cash'])
    return 0.0

def update_cash(val, p_name):
    supabase.table("portfolios").update({"cash": val}).eq("name", p_name).execute()

def store_trade(trade, p_name):
    # Pickle and convert to hex string for Postgres BYTEA compatibility
    trade_data_hex = pickle.dumps(trade).hex()
    
    payload = {
        "trade_id": trade.trade_id,
        "portfolio_name": p_name,
        "data": trade_data_hex
    }
    # .upsert() handles the "INSERT OR REPLACE" logic
    supabase.table("trades").upsert(payload).execute()

def get_trade_by_id(trade_id, p_name):
    response = supabase.table("trades").select("data").eq("trade_id", trade_id).eq("portfolio_name", p_name).execute()
    if response.data:
        hex_data = response.data[0]['data']
        # Convert hex back to bytes before unpickling
        # Note: Depending on Supabase driver version, it might return a memoryview or string
        raw_bytes = bytes.fromhex(hex_data) if isinstance(hex_data, str) else bytes(hex_data)
        return pickle.loads(raw_bytes)
    return None

def get_trades(p_name):
    response = supabase.table("trades").select("data").eq("portfolio_name", p_name).execute()
    trades_list = []
    for row in response.data:
        hex_data = row['data']
        raw_bytes = bytes.fromhex(hex_data) if isinstance(hex_data, str) else bytes(hex_data)
        trades_list.append(pickle.loads(raw_bytes))
    return trades_list

def delete_trade(trade_id):
    supabase.table("trades").delete().eq("trade_id", trade_id).execute()

def get_portfolio_val(p_name):
    cash = get_cash(p_name)
    trades = get_trades(p_name)
    credit_trades = {"csp", "cc", "short_put", "short_call"}
    val = cash
    for trade in trades:
        if trade.trade_type not in credit_trades:
            val += trade.value
    return val