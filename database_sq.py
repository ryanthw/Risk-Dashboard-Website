import sqlite3
import pickle
import os

DB_PATH = "data/portfolio.db"

# Ensure the data directory exists
os.makedirs("data", exist_ok=True)

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    # This line is the missing piece:
    conn.execute("PRAGMA foreign_keys = ON") 
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolios (
                name TEXT PRIMARY KEY,
                cash REAL DEFAULT 0.0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                portfolio_name TEXT,
                data BLOB,
                FOREIGN KEY (portfolio_name) REFERENCES portfolios(name) ON DELETE CASCADE
            )
        """)

def get_portfolios():
    with get_connection() as conn:
        cursor = conn.execute("SELECT name FROM portfolios")
        return [row['name'] for row in cursor.fetchall()]

def build_portfolio(name):
    # Strip whitespace to prevent "Test" and "Test " being treated differently
    name = name.strip()
    with get_connection() as conn:
        try:
            conn.execute("INSERT INTO portfolios (name, cash) VALUES (?, 0.0)", (name,))
            conn.commit()
        except sqlite3.IntegrityError:
            # This is the specific error for a Duplicate Name (Primary Key)
            raise ValueError("Portfolio name already exists.")

def delete_portfolio(p_name):
    with get_connection() as conn:
        # 1. Manually wipe trades associated with this name
        conn.execute("DELETE FROM trades WHERE portfolio_name = ?", (p_name,))
        # 2. Wipe the portfolio itself
        conn.execute("DELETE FROM portfolios WHERE name = ?", (p_name,))
        # 3. Explicitly commit (though 'with' usually handles this, it's safer)
        conn.commit()

def get_cash(p_name):
    with get_connection() as conn:
        row = conn.execute("SELECT cash FROM portfolios WHERE name = ?", (p_name,)).fetchone()
        return row['cash'] if row else 0.0

def update_cash(val, p_name):
    with get_connection() as conn:
        conn.execute("UPDATE portfolios SET cash = ? WHERE name = ?", (val, p_name))

def store_trade(trade, p_name):
    # We pickle the whole object to keep your Trade class logic intact
    trade_data = pickle.dumps(trade)
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO trades (trade_id, portfolio_name, data) 
            VALUES (?, ?, ?)
        """, (trade.trade_id, p_name, trade_data))

def get_trade_by_id(trade_id, p_name):
    """Fetch a specific trade object from the database."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT data FROM trades WHERE trade_id = ? AND portfolio_name = ?", (trade_id, p_name))
        row = cursor.fetchone()
        return pickle.loads(row['data']) if row else None

def get_trades(p_name):
    with get_connection() as conn:
        cursor = conn.execute("SELECT data FROM trades WHERE portfolio_name = ?", (p_name,))
        return [pickle.loads(row['data']) for row in cursor.fetchall()]

def delete_trade(trade_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM trades WHERE trade_id = ?", (trade_id,))

def get_portfolio_val(p_name):
    cash = get_cash(p_name)
    trades = get_trades(p_name)
    # Reuse your existing logic for credit trades
    credit_trades = {"csp", "cc", "short_put", "short_call"}
    val = cash
    for trade in trades:
        if trade.trade_type not in credit_trades:
            val += trade.value
    return val

# Initialize the DB automatically when this module is imported
init_db()