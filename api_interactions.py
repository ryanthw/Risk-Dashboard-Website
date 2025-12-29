import streamlit as st
import finnhub

def get_price(ticker):
    # Access key from .streamlit/secrets.toml
    api_key = st.secrets["FINNHUB_API_KEY"]
    client = finnhub.Client(api_key=api_key)
    quote = client.quote(ticker.upper())
    return quote['c']