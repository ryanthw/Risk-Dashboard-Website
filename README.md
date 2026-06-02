# Options & Stock Risk Dashboard

A comprehensive, institutional-grade trading risk management platform built with Streamlit and powered by a Supabase SQL backend. This dashboard allows traders to manage multiple portfolios, analyze complex option strategies (including vertical spreads and the Wheel strategy), and visualize risk through advanced Monte Carlo simulations and historical snapshots.

## 🚀 Features

### 1. Multi-Portfolio Management
- **Centralized Control:** Create, switch, and delete multiple portfolios.
- **Cash Tracking:** Manage cash balances per portfolio for accurate leverage and exposure calculations.
- **Trade Lifecycle:** Add, update, and close trades. Closing trades archives them into a historical record for performance analysis.

### 2. Advanced Risk Analytics
- **The "Big 5" Metrics:**
    - **Total Value:** Real-time mark-to-market valuation.
    - **Gross Exposure:** Sum of maximum possible losses across all positions.
    - **Net Liquidity:** Immediate cash value if all positions were closed.
    - **HHI (Herfindahl-Hirschman Index):** Concentration metric to ensure ticker diversification.
    - **Open Trades:** Count of active positions currently being managed.
- **Performance Multipliers:** Compare expected returns against S&P 500 benchmarks (Long-term and Short-term Alpha).
- **Institutional Vitals:** Track Beta-Weighted Delta (portfolio bias), Daily Theta (time decay), and Leverage Ratios.

### 3. Strategy & Visual Analysis
- **Monte Carlo Simulations:** Empirical Probability of Profit (POP) and Expected Profit calculations for all option strategies.
- **Visual Risk Profiling:** 
    - Scatter plots for Risk-Reward profiles.
    - Capital-at-risk bar charts by expiration.
    - Portfolio risk allocation pie charts and treemaps by sector.
- **Wealth Forecasting:** 10-year wealth projection based on annualized expected returns.
- **Sector Treemaps:** Visualize capital allocation across different market sectors.

### 4. Strategy Sandbox & Scanner
- **Trade Analysis Sandbox:** Simulate complex trades (shares, CSPs, Spreads, etc.) before execution. Analyze their impact on portfolio Delta, HHI, and sector exposure.
- **Income Driver Scanner:** Scan watchlists for "Wheel Strategy" opportunities based on Implied Volatility (IV), share price, and sector diversification.

### 5. Historical Tracking
- **Portfolio Snapshots:** Log daily snapshots of Net Liquidity, Weighted Delta, and Expected Profit.
- **Performance Over Time:** Interactive line charts of historical portfolio value.
- **Trade History:** Full archive of closed positions with realized P&L and IV at close.

---

## 🛠️ Technical Architecture

### Frontend: Streamlit
The user interface is built using [Streamlit](https://streamlit.io/), providing a reactive and "monospaced" professional aesthetic.
- **Layout:** Multi-page application structure (`pages/` directory).
- **Visualizations:** Powered by [Plotly](https://plotly.com/) for interactive, high-fidelity financial charts.
- **Custom CSS:** Injected for a polished, dark-themed dashboard look.

### Backend: Supabase (PostgreSQL)
All data is persisted in a [Supabase](https://supabase.com/) database.
- **Authentication:** Integrated Supabase Auth for secure user login and signup.
- **Data Model:**
    - `portfolios`: Stores portfolio metadata and cash balances.
    - `trades`: Stores active positions (using Python's `pickle` for complex object serialization).
    - `history_trades`: Archive of realized trades.
    - `history_snapshots`: Daily portfolio metric logs.
- **RLS (Row Level Security):** Ensures users only access their own data.

### Market Data & Calculations
- **APIs:** 
    - [Finnhub](https://finnhub.io/) for real-time price quotes, sector info, and company profiles.
    - [yfinance](https://github.com/ranaroussi/yfinance) for historical volatility and correlation data.
- **Math Engine:** Custom Monte Carlo simulator (`trade.py`) using `numpy` and `scipy` for GBM (Geometric Brownian Motion) terminal price projections.

---

## 📂 Project Structure

```text
├── Dashboard.py            # Main entry point & Portfolio management
├── trade.py                # Core Trade class & Monte Carlo logic
├── utils.py                # Portfolio-level risk & math functions
├── database_sq.py          # Supabase CRUD operations
├── api_interactions.py     # Finnhub & yfinance API wrappers
├── pages/                  # Dashboard Sub-pages
│   ├── 01_Visuals.py       # P&L Distributions & Risk Charts
│   ├── 02_Strategy.py      # Sector Allocation & Opportunity Scanner
│   ├── 03_History.py       # Portfolio Value Over Time
│   └── 04_Trade_Analysis.py# Sandbox for trade simulation
└── requirements.txt        # Python dependencies
```

---

## 🛠️ Setup & Hosting

1. **Environment Variables:**
   The application requires the following secrets in `.streamlit/secrets.toml`:
   ```toml
   SUPABASE_URL = "your_supabase_url"
   SUPABASE_KEY = "your_supabase_anon_key"
   FINNHUB_API_KEY = "your_finnhub_key"
   ```

2. **Installation:**
   ```bash
   pip install -r requirements.txt
   streamlit run Dashboard.py
   ```

3. **Hosting:**
   Optimized for deployment on **Streamlit Community Cloud** or any cloud provider supporting Docker/Python (e.g., Railway, Render). Supabase provides the persistent SQL layer, making the frontend effectively stateless.
