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

@st.cache_data(ttl=600)
def get_portfolios(user_id):
    response = supabase.table("portfolios").select("name").eq("user_id", user_id).execute()
    return [row['name'] for row in response.data]

def build_portfolio(user_id, name):
    name = name.strip()
    response = supabase.table("portfolios").insert({"user_id": user_id, "name": name, "cash": 0.0}).execute()
    
    if hasattr(response, 'error') and response.error:
        raise ValueError(f"Could not create portfolio: {response.error.message}")
    
    st.cache_data.clear()

def delete_portfolio(user_id, p_name):
    # RLS and Cascade should handle this, but being explicit.
    supabase.table("portfolios").delete().eq("user_id", user_id).eq("name", p_name).execute()
    st.cache_data.clear()

@st.cache_data(ttl=600)
def get_cash(user_id, p_name):
    response = supabase.table("portfolios").select("cash").eq("user_id", user_id).eq("name", p_name).execute()
    if response.data:
        return float(response.data[0]['cash'])
    return 0.0

def update_cash(user_id, val, p_name):
    supabase.table("portfolios").update({"cash": float(val)}).eq("user_id", user_id).eq("name", p_name).execute()
    st.cache_data.clear()

def store_trade(user_id, trade, p_name):
    trade_data_hex = pickle.dumps(trade).hex()
    
    payload = {
        "trade_id": trade.trade_id,
        "user_id": user_id,
        "portfolio_name": p_name,
        "data": trade_data_hex
    }
    supabase.table("trades").upsert(payload).execute()
    st.cache_data.clear()

def get_trade_by_id(user_id, trade_id, p_name):
    response = supabase.table("trades").select("data").eq("user_id", user_id).eq("trade_id", trade_id).eq("portfolio_name", p_name).execute()
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
def get_trades(user_id, p_name):
    response = supabase.table("trades").select("data").eq("user_id", user_id).eq("portfolio_name", p_name).execute()
    
    trades_list = []
    for row in response.data:
        hex_data = row['data']
        try:
            if isinstance(hex_data, str):
                if hex_data.startswith('\\x'):
                    hex_data = hex_data[2:]
                actual_binary = bytes.fromhex(hex_data)
                trades_list.append(pickle.loads(actual_binary))
        except Exception as e:
            print(f"Error decoding trade row: {e}")
            continue
            
    return trades_list

def delete_trade(user_id, trade_id):
    supabase.table("trades").delete().eq("user_id", user_id).eq("trade_id", trade_id).execute()
    st.cache_data.clear()

def get_portfolio_val(user_id, p_name):
    val = get_cash(user_id, p_name)
    trades = get_trades(user_id, p_name)
    credit_trades = {"csp", "cc", "short_put", "short_call", "pcs", "ccs"}
    for trade in trades:
        if trade.trade_type not in credit_trades:
            val += trade.value
    return val

def archive_trade(user_id, p_name, trade_obj, realized_pnl):
    try:
        if realized_pnl is None:
            realized_pnl = 0.0
            
        entry_dt = getattr(trade_obj, 'opened', None)
        if isinstance(entry_dt, datetime):
            entry_dt = entry_dt.isoformat()
            
        exit_dt = datetime.now().isoformat()

        data = {
            "user_id": user_id,
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
        print(f"Error archiving trade: {e}")
        return False

def record_portfolio_snapshot(user_id, p_name, metrics):
    try:
        metrics["user_id"] = user_id
        metrics["portfolio_name"] = p_name
        supabase.table("history_snapshots").insert(metrics).execute()
        return True
    except Exception as e:
        print(f"Error recording snapshot: {e}")
        return False
    
def check_snapshot_exists(user_id, p_name, date_str):
    res = supabase.table("history_snapshots")\
        .select("id")\
        .eq("user_id", user_id)\
        .eq("portfolio_name", p_name)\
        .gte("timestamp", f"{date_str}T00:00:00")\
        .lte("timestamp", f"{date_str}T23:59:59")\
        .execute()
    return len(res.data) > 0

@st.cache_data(ttl=600)
def get_historical_snapshots(user_id, p_name):
    response = supabase.table("history_snapshots")\
        .select("*")\
        .eq("user_id", user_id)\
        .eq("portfolio_name", p_name)\
        .order("timestamp", desc=False)\
        .execute()
    return response.data
