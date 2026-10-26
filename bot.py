import time
import os
import yfinance as yf
import alpaca_trade_api as tradeapi

# 1. API Keys (Free Paper Trading account from alpaca.markets)
API_KEY = os.getenv("ALPACA_KEY", "YOUR_ALPACA_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET", "YOUR_ALPACA_SECRET")
BASE_URL = "https://paper-api.alpaca.markets"

# 2. Risk & Strategy Parameters
TICKER = "TSLA"          # Target asset
MAX_DOLLAR_RISK = 50.0   # Maximum risk per trade ($50)
TIMEFRAME = "5m"

api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL, api_version='v2')

def evaluate_and_trade():
    try:
        # Check current positions to prevent double buying
        positions = [p.symbol for p in api.list_positions()]
        if TICKER in positions:
            print(f"[{TICKER}] Position already open. Skipping scan.")
            return

        # Fetch latest intraday data
        df = yf.download(TICKER, period="1d", interval=TIMEFRAME, progress=False)
        if len(df) < 4:
            print("Not enough bars yet today.")
            return

        # Compute 15-minute Opening Range (first 3 x 5-minute bars)
        orb_high = float(df['High'].iloc[:3].max())
        orb_low = float(df['Low'].iloc[:3].min())
        latest_close = float(df['Close'].iloc[-1])

        print(f"[{TICKER}] Latest: ${latest_close:.2f} | ORB High: ${orb_high:.2f} | ORB Low: ${orb_low:.2f}")

        # Breakout Trigger: Latest 5-min bar closes above the ORB High
        if latest_close > orb_high:
            stop_price = round((orb_high + orb_low) / 2.0, 2)
            risk_per_share = latest_close - stop_price

            if risk_per_share <= 0:
                return

            # Share calculation based on exact risk budget
            shares = int(MAX_DOLLAR_RISK // risk_per_share)
            if shares < 1:
                shares = 1

            target_price = round(latest_close + (risk_per_share * 2.0), 2)

            print(f"\n>>> [AI TRIGGERED TRADE] Buying {shares} {TICKER} @ ${latest_close:.2f}")
            print(f">>> Stop-Loss: ${stop_price:.2f} | Target 2R: ${target_price:.2f}\n")

            # Autonomous Bracket Order execution
            api.submit_order(
                symbol=TICKER,
                qty=shares,
                side='buy',
                type='market',
                time_in_force='gtc',
                order_class='bracket',
                stop_loss={'stop_price': stop_price},
                take_profit={'limit_price': target_price}
            )
            print(">>> Order successfully submitted to broker.")

    except Exception as e:
        print(f"Loop Error: {e}")

if __name__ == "__main__":
    print("AI Trader is running autonomously...")
    while True:
        evaluate_and_trade()
        time.sleep(300)  # Check every 5 minutes
