from trade import Trade
import database_sq as database 
import api_interactions as api
import yfinance as yf
import numpy as np

# Risk Section Metrics
def get_percent_exposure(p_name) -> float:
    exp = get_gross_exposure(p_name)
    val = database.get_portfolio_val(p_name)
    return (exp / val) * 100 if val > 0 else 0.0

def get_gross_exposure(p_name) -> float:
    trades = database.get_trades(p_name)
    cumm_exposure = 0.0
    for trade in trades:
        cumm_exposure += trade.max_loss
    return cumm_exposure

def get_cash_percent(p_name) -> float:
    cash = database.get_cash(p_name)
    total_val = database.get_portfolio_val(p_name)
    return (cash / total_val * 100) if total_val > 0 else 0.0

def get_cash_to_pos_ratio(p_name) -> float:
    cash = database.get_cash(p_name)
    # We use get_trades and calculate value since get_positional_val 
    # might not be in the new database_sq.py yet
    trades = database.get_trades(p_name)
    pos_val = sum(t.value for t in trades)
    return (cash / pos_val) if pos_val > 0 else 1.0

def get_leverage_ratio(p_name) -> float:
    exposure = get_gross_exposure(p_name)
    port_val = database.get_portfolio_val(p_name)
    return (exposure / port_val) if port_val > 0 else 0.0

def get_highest_pos_percent(p_name) -> float:
    highest_val = 0.0
    total_val = database.get_portfolio_val(p_name)
    positions = database.get_trades(p_name)
    for pos in positions:
        if highest_val < pos.max_loss:
            highest_val = pos.max_loss
    return (highest_val / total_val * 100) if total_val > 0 else 0.0

def get_hhi(p_name) -> float:
    exp = get_gross_exposure(p_name)
    hhi = 0.0
    positions = database.get_trades(p_name)

    if exp <= 0 or not positions:
        return 0.0
    
    tickers = {}
    
    for pos in positions:
        if pos.ticker in tickers:
            tickers[pos.ticker] += pos.max_loss
        else:
            tickers[pos.ticker] = pos.max_loss
    
    for ticker, loss in tickers.items():
        ticker_weight = loss / exp
        hhi += ticker_weight ** 2
    
    return hhi

def get_expected_returns(rets) -> float:
    return sum(rets)

def get_max_profit(p_name) -> float:
    max_p = 0.0
    positions = database.get_trades(p_name)
    for pos in positions:
        max_p += pos.max_gain
    return max_p

def get_risk_reward_ratio(p_name) -> float:
    max_p = get_max_profit(p_name)
    max_l = get_gross_exposure(p_name)
    return (max_l / max_p) if max_p > 0 else 0.0

def get_port_expected_return(p_name) -> float:
    base = database.get_trades(p_name)
    total_val_port = database.get_portfolio_val(p_name)

    if total_val_port <= 0.0:
        return 0.0
    
    expected_ret = 0.0

    for pos in base:
        if pos.value == 0.0 or pos.pnl_dist is None:
            continue

        pos_val = pos.value
        expected_prof = pos.expected_profit
        e_r = expected_prof / pos_val if pos_val > 0 else 0.0
        w = pos_val / total_val_port
        expected_ret += w * e_r
    return expected_ret

def get_port_downside_variance(p_name, target_return) -> float:
    trades = database.get_trades(p_name)
    total_val_port = database.get_portfolio_val(p_name)

    if total_val_port <= 0.0:
        return 0.0
    
    downside_var = 0.0

    for pos in trades:
        pos_val = pos.value
        if pos_val <= 0 or pos.pnl_dist is None:
            continue

        w = pos_val / total_val_port
        r = pos.pnl_dist

        # Downside deviation per Sortino definition
        downside = np.minimum(0.0, r - target_return)

        # Portfolio aggregation (variance scales with w^2)
        downside_var += (w ** 2) * np.mean(downside ** 2)

    return downside_var

def get_sortino_ratio(p_name) -> float:
    er = get_port_expected_return(p_name)
    downside_var = get_port_downside_variance(p_name, 0.0)

    if downside_var <= 0:
        return 0.0
    
    return er / np.sqrt(downside_var)

def get_er_percent(ers, p_name) -> float:
    er = get_expected_returns(ers)
    port_val = database.get_portfolio_val(p_name)
    return (er / port_val) * 100 if port_val > 0 else 0.0

def get_er_ann(p_name) -> float:
    # Calculates weighted avg of ERPA across all non-stock and cc positions
    avg_er_ann = 0.0
    port_val = database.get_portfolio_val(p_name)
    positions = database.get_trades(p_name)

    if len(positions) == 0 or port_val <= 0:
        return 0.0

    for pos in positions:
        if pos.trade_type not in ["shares", "cc"] and pos.max_loss > 0:
            # Check if pos_len is zero to avoid division by zero
            days = pos.pos_len if pos.pos_len > 0 else 1
            cycle_yield = pos.expected_profit / abs(pos.max_loss)
            er_ann = cycle_yield * (365 / days)
            w = abs(pos.max_loss) / port_val
            avg_er_ann += w * er_ann
    
    return avg_er_ann

# Util method for net liquidity
def get_net_liquidity(p_name) -> float:
    val = database.get_portfolio_val(p_name)
    cost_to_close = get_cost_to_close_shorts(p_name)
    return val - cost_to_close

def get_cost_to_close_shorts(p_name) -> float:
    trades = database.get_trades(p_name)
    cost = 0.0
    for trade in trades:
        if trade.trade_type in ["csp", "cc", "short_call", "short_put"]:
            price = trade.value - trade.expected_profit
            cost += price
    return cost

# Positional Metrics
def get_percent_risk_position(position: Trade, p_name) -> float:
    max_loss_port = database.get_portfolio_val(p_name)
    max_loss_pos = position.max_loss
    return (max_loss_pos / max_loss_port) * 100 if max_loss_port > 0 else 0.

# Update Underlying Price for all Positions
def update_underlyings(p_name):
    positions = database.get_trades(p_name)

    # Limit API calls by building dict of tickers, prices
    tickers_prices = {}
    tickers_iv = {}
    for pos in positions:
        if pos.ticker in tickers_prices:
            continue
        tickers_prices[pos.ticker] = api.get_price(pos.ticker)
        if pos.trade_type == "shares":
            tickers_iv[pos.ticker] = api.get_historical_volatility(pos.ticker)
    
    for pos in positions:
        if tickers_prices[pos.ticker] > 0:
            pos.underlying_price = float(f"{tickers_prices[pos.ticker]:.2f}")
        if pos.trade_type == "shares":
            pos.iv = tickers_iv[pos.ticker]
        pos.refresh_pnl()
        database.store_trade(pos, p_name)