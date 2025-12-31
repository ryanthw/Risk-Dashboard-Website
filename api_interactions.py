import streamlit as st
import finnhub
import yfinance as yf
import numpy as np

def get_price(ticker):
    # Access key from .streamlit/secrets.toml
    api_key = st.secrets["FINNHUB_API_KEY"]
    client = finnhub.Client(api_key=api_key)
    quote = client.quote(ticker.upper())
    return quote['c']

def get_historical_volatility(ticker_symbol, window=30):
    """
    Fetches historical data via yfinance and calculates annualized volatility.
    :param ticker_symbol: Stock ticker (e.g., 'AAPL')
    :param window: Number of days to look back (default 30)
    :return: Annualized volatility as a decimal (e.g., 0.25 for 25%)
    """
    try:
        # 1. Download data (we fetch slightly more to ensure we have 'window' daily returns)
        data = yf.download(ticker_symbol, period="60d", interval="1d", progress=False)
        
        if data.empty or len(data) < window:
            return 0.30  # Default fallback (30% is a safe market average)

        # 2. Calculate Daily Log Returns
        # Formula: ln(Price_t / Price_t-1)
        close_prices = data['Close'].tail(window + 1)
        log_returns = np.log(close_prices / close_prices.shift(1)).dropna()

        # 3. Calculate Standard Deviation and Annualize
        # 252 is the standard number of trading days in a year
        daily_std = log_returns.std()
        annualized_vol = daily_std * np.sqrt(252)

        return float(annualized_vol.iloc[0])
    
    except Exception as e:
        print(f"Error fetching vol for {ticker_symbol}: {e}")
        return 0.30