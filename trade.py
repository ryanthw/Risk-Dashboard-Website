from datetime import datetime
import uuid
from math import sqrt
import api_interactions as api
import numpy as np

class Trade:
    def __init__(
        self,
        trade_type: str,     # "shares", "csp", "cc", "short_call", "short_put", etc.
        ticker: str,
        qty: int,
        strike: float | None,
        premium: float | None,      # credit (positive) or debit (negative)
        expiration: datetime,
        underlying_price: float | None,
        iv: float,          # decimal (0.20 = 20%)
    ):
        self.trade_id = str(uuid.uuid4())
        self.trade_type = trade_type
        self.ticker = ticker.upper()
        self.qty = qty
        self.strike = strike
        self.premium = premium
        self.expiration = datetime.strptime(expiration, "%Y-%m-%d")
        self.underlying_price = underlying_price if underlying_price else api.get_price(self.ticker)
        self.iv = iv if self.trade_type != "shares" else api.get_historical_volatility(self.ticker)
        self.opened = datetime.now()
        self.pnl_dist = self.simulate_payoff(100000, 0.0)

    # ------------------------
    # Computed risk properties
    # ------------------------

    @property
    def dte(self):
        delta = self.expiration - datetime.now()
        return delta.total_seconds() / 86400.0   # fractional days
    
    @property
    def pos_len(self):
        delta = self.expiration - self.opened
        return delta.total_seconds() / 86400.0   # fractional days representing position timeline


    @property
    def value(self):
        if self.trade_type == "shares":
            return self.underlying_price * self.qty

        # options — approx 100 multiplier
        return abs(self.premium) * 100 * self.qty

    # -------------------------------------
    # Max Gain / Max Loss by strategy type
    # -------------------------------------
    @property
    def max_gain(self):
        t = self.trade_type

        if t == "shares":
            return float(self.value * .5)

        if t == "csp":  # cash-secured put
            return self.premium * 100 * self.qty

        if t == "cc":  # covered call
            return ((self.strike - self.underlying_price) + self.premium) * 100 * self.qty

        if t == "short_put":
            return self.premium * 100 * self.qty

        if t == "short_call":
            return self.premium * 100 * self.qty

        # long options
        if t == "long_call":
            return float(self.premium * 4)
        if t == "long_put":
            return (self.strike * 100 * self.qty)

        return 0

    @property
    def max_loss(self):
        t = self.trade_type

        if t == "shares":
            return self.underlying_price * self.qty

        if t == "csp":
            return (self.strike - self.premium) * 100 * self.qty

        if t == "cc":
            # Because of the way I set CC strikes, should be no loss possible
            return 0.0

        if t == "short_put":
            return (self.strike - self.premium) * 100 * self.qty

        if t == "short_call":
            # undefined (naked short call)
            return float("inf")

        if t == "long_call":
            return self.premium * 100 * self.qty

        if t == "long_put":
            return self.premium * 100 * self.qty

        return 0
    
    # ---------------------------
    # Refresher for pnl_dist
    # ---------------------------
    def refresh_pnl(self):
        # Refresh pnl distribution field
        self.pnl_dist = self.simulate_payoff(100000, 0.0)


    # ---------------------------
    # Monte Carlo and POP Helpers
    # ---------------------------
    def simulate_payoff(self, sims=100000, mu=0.0):
        """
        Monte Carlo payoff simulator for all Trade types.
        Returns simulated terminal P&L array.
        """

        # extract params from trade object
        S0 = self.underlying_price
        K = self.strike
        iv = self.iv
        T = 0
        if self.trade_type == "shares":
            T = 1
        else:
            T = max(self.dte, 0) / 365.0 
        qty = self.qty
        premium = self.premium    # credit = +, debit = -

        # Generate terminal prices under GBM
        # Antithetic variates for variance reduction
        half = sims // 2
        Z = np.random.normal(size=half)
        Z_full = np.concatenate([Z, -Z])

        ST = S0 * np.exp((mu - 0.5 * iv**2) * T + iv * np.sqrt(T) * Z_full)

        # ================================
        # PAYOFF LOGIC BY TRADE TYPE
        # ================================
        payoff = np.zeros_like(ST)

        t = self.trade_type.lower()

        # ----- Long Call -----
        if t == "long_call":
            payoff = np.maximum(ST - K, 0) * 100 * qty - premium * 100 * qty

        # ----- Long Put -----
        elif t == "long_put":
            payoff = np.maximum(K - ST, 0) * 100 * qty - premium * 100 * qty

        # ----- Short Call -----
        elif t == "short_call":
            payoff = -np.maximum(ST - K, 0) * 100 * qty + premium * 100 * qty

        # ----- Short Put -----
        elif t == "short_put":
            payoff = -np.maximum(K - ST, 0) * 100 * qty + premium * 100 * qty

        # ----- Covered Call -----
        elif t == "cc":
            # long stock + short call
            stock_pnl = (ST - S0) * qty
            call_pnl = -np.maximum(ST - K, 0) * 100 * qty + premium * 100 * qty
            payoff = stock_pnl + call_pnl

        # ----- Cash Secured Put -----
        elif t == "csp":
            payoff = -np.maximum(K - ST, 0) * 100 * qty + premium * 100 * qty

        # ----- Shares Only -----
        elif t == "shares":
            payoff = (ST - S0) * qty

        else:
            raise ValueError(f"Unsupported trade type: {self.trade_type}")

        return payoff


    # ===============================================================
    # POP and Expected Profit (DROP THESE DIRECTLY INTO Trade CLASS)
    # ===============================================================
    @property
    def pop(self):
        """ Empirical Probability of Profit using Monte Carlo """
        pnl = self.pnl_dist
        if pnl is None:
            return 0.0
        return float(np.mean(pnl > 0))


    @property
    def expected_profit(self):
        """ Expected terminal P&L (mean of payoff distribution) """
        pnl = self.pnl_dist
        if pnl is None:
            return 0.0
        return float(np.mean(pnl))
    
    # To String
    def __str__(self):
        return f"{self.ticker}, value: {self.value:.2f}"