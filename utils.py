from trade import Trade
import database_sq as database 
import api_interactions as api
import yfinance as yf
import numpy as np
from datetime import datetime

# Risk Section Metrics
def get_percent_exposure(user_id, p_name) -> float:
    exp = get_gross_exposure(user_id, p_name)
    val = database.get_portfolio_val(user_id, p_name)
    return (exp / val) * 100 if val > 0 else 0.0

def get_gross_exposure(user_id, p_name) -> float:
    trades = database.get_trades(user_id, p_name)
    cumm_exposure = 0.0
    for trade in trades:
        cumm_exposure += trade.max_loss
    return cumm_exposure

def get_cash_percent(user_id, p_name) -> float:
    cash = database.get_cash(user_id, p_name)
    total_val = database.get_portfolio_val(user_id, p_name)
    return (cash / total_val * 100) if total_val > 0 else 0.0

def get_cash_to_pos_ratio(user_id, p_name) -> float:
    cash = database.get_cash(user_id, p_name)
    trades = database.get_trades(user_id, p_name)
    pos_val = sum(t.value for t in trades)
    return (cash / pos_val) if pos_val > 0 else 1.0

def get_leverage_ratio(user_id, p_name) -> float:
    exposure = get_gross_exposure(user_id, p_name)
    port_val = database.get_portfolio_val(user_id, p_name)
    return (exposure / port_val) if port_val > 0 else 0.0

def get_highest_pos_percent(user_id, p_name) -> float:
    highest_val = 0.0
    total_val = database.get_portfolio_val(user_id, p_name)
    positions = database.get_trades(user_id, p_name)
    for pos in positions:
        if highest_val < pos.max_loss:
            highest_val = pos.max_loss
    return (highest_val / total_val * 100) if total_val > 0 else 0.0

def get_hhi(user_id, p_name) -> float:
    exp = get_gross_exposure(user_id, p_name)
    hhi = 0.0
    positions = database.get_trades(user_id, p_name)

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

def get_max_profit(user_id, p_name) -> float:
    max_p = 0.0
    positions = database.get_trades(user_id, p_name)
    for pos in positions:
        max_p += pos.max_gain
    return max_p

def get_risk_reward_ratio(user_id, p_name) -> float:
    max_p = get_max_profit(user_id, p_name)
    max_l = get_gross_exposure(user_id, p_name)
    return (max_l / max_p) if max_p > 0 else 0.0

def get_port_expected_return(user_id, p_name) -> float:
    base = database.get_trades(user_id, p_name)
    total_val_port = database.get_portfolio_val(user_id, p_name)

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

def get_port_downside_variance(user_id, p_name, target_return) -> float:
    trades = database.get_trades(user_id, p_name)
    total_val_port = database.get_portfolio_val(user_id, p_name)

    if total_val_port <= 0.0:
        return 0.0
    
    downside_var = 0.0

    for pos in trades:
        pos_val = pos.value
        if pos_val <= 0 or pos.pnl_dist is None:
            continue

        w = pos_val / total_val_port
        r = pos.pnl_dist

        downside = np.minimum(0.0, r - target_return)
        downside_var += (w ** 2) * np.mean(downside ** 2)

    return downside_var

def get_sortino_ratio(user_id, p_name) -> float:
    er = get_port_expected_return(user_id, p_name)
    downside_var = get_port_downside_variance(user_id, p_name, 0.0)

    if downside_var <= 0:
        return 0.0
    
    return er / np.sqrt(downside_var)

def get_er_percent(user_id, ers, p_name) -> float:
    er = get_expected_returns(ers)
    port_val = database.get_portfolio_val(user_id, p_name)
    return (er / port_val) * 100 if port_val > 0 else 0.0

def get_er_ann(user_id, p_name) -> float:
    avg_er_ann = 0.0
    port_val = database.get_portfolio_val(user_id, p_name)
    positions = database.get_trades(user_id, p_name)

    if len(positions) == 0 or port_val <= 0:
        return 0.0

    for pos in positions:
        if pos.trade_type not in ["shares", "cc"]:
            days = pos.pos_len if pos.pos_len > 0 else 1
            cycle_yield = pos.expected_profit / abs(pos.max_loss)
            er_ann = cycle_yield * (365 / days)
            w = abs(pos.max_loss) / port_val
            avg_er_ann += w * er_ann
    
    return avg_er_ann

def get_net_liquidity(user_id, p_name) -> float:
    liq = database.get_cash(user_id, p_name)
    positions = database.get_trades(user_id, p_name)
    for pos in positions:
        if pos.trade_type == "shares":
            liq += pos.value
    liq -= get_cost_to_close_shorts(positions)
    liq += get_long_options_vals(positions)
    return liq

def get_cost_to_close_shorts(trades) -> float:
    cost = 0.0
    for trade in trades:
        if trade.trade_type in ["csp", "cc", "short_call", "short_put", "pcs", "ccs"]:
            price = trade.value - trade.expected_profit
            cost += price
    return cost

def get_long_options_vals(trades) -> float:
    cost = 0.0
    for trade in trades:
        if trade.trade_type in ["long_call", "long_put", "cds", "pds"]:
            price = trade.value + trade.expected_profit
            cost += price
    return cost

def get_undeployed_cash(user_id, p_name) -> float:
    trades = database.get_trades(user_id, p_name)
    cash = database.get_cash(user_id, p_name)
    for trade in trades:
        if trade.trade_type in ["csp", "pcs", "ccs"]:
            cash -= trade.max_loss
    return cash

def get_portfolio_beta_delta(user_id, p_name) -> float:
    trades = database.get_trades(user_id, p_name)
    if not trades:
        return 0.0

    total_beta_delta = 0.0

    for t in trades:
        beta = api.get_stock_beta(t.ticker)
        raw_delta = 0.0
        t_type = t.trade_type.lower()
        qty = t.qty
        
        if t_type == "shares":
            raw_delta = qty 
        elif t_type in ["csp", "short_put"]:
            raw_delta = 0.50 * 100 * qty 
        elif t_type in ["cc", "short_call"]:
            raw_delta = -0.50 * 100 * qty 
        elif t_type == "pcs":
            raw_delta = 0.25 * 100 * qty 
        elif t_type == "ccs":
            raw_delta = -0.25 * 100 * qty 
        elif t_type == "long_call" or t_type == "cds":
            raw_delta = 0.40 * 100 * qty 
        elif t_type == "long_put" or t_type == "pds":
            raw_delta = -0.40 * 100 * qty 

        total_beta_delta += (raw_delta * beta)

    return total_beta_delta

def get_percent_risk_position(user_id, position: Trade, p_name) -> float:
    max_loss_port = database.get_portfolio_val(user_id, p_name)
    max_loss_pos = position.max_loss
    return (max_loss_pos / max_loss_port) * 100 if max_loss_port > 0 else 0.

def update_underlyings(user_id, p_name):
    positions = database.get_trades(user_id, p_name)

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
        if pos.trade_type == "shares" and pos.ticker in tickers_iv:
            pos.iv = tickers_iv[pos.ticker] 
        pos.refresh_pnl()
        database.store_trade(user_id, pos, p_name)

def capture_and_save_snapshot(user_id, p_name):
    now = datetime.now()
    today_iso = now.date().isoformat()
    
    if database.check_snapshot_exists(user_id, p_name, today_iso):
        print(f"Snapshot already exists for {p_name} today. Skipping log.")
        return False

    try:
        trades = database.get_trades(user_id, p_name)
        net_liq = get_net_liquidity(user_id, p_name)
        weighted_delta = get_portfolio_beta_delta(user_id, p_name)
        total_exp_profit = sum([t.expected_profit for t in trades if t.trade_type != 'shares'])
        port_val = database.get_portfolio_val(user_id, p_name)
        erpa = (total_exp_profit / port_val) if port_val > 0 else 0.0

        # Standardize timestamp to 4:00 PM of the current calendar day
        standardized_dt = now.replace(hour=16, minute=0, second=0, microsecond=0)

        snapshot_metrics = {
            "timestamp": standardized_dt.isoformat(),
            "net_liquidity": net_liq,
            "weighted_delta": weighted_delta,
            "expected_profit_total": total_exp_profit,
            "erpa": erpa
        }

        success = database.record_portfolio_snapshot(user_id, p_name, snapshot_metrics)
        return success

    except Exception as e:
        print(f"Failed to capture snapshot: {e}")
        return False
