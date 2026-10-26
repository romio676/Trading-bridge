import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import yfinance as yf
import alpaca_trade_api as tradeapi

# 1. API Keys (Alpaca Paper Trading)
API_KEY = os.getenv("ALPACA_KEY", "YOUR_ALPACA_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET", "YOUR_ALPACA_SECRET")
BASE_URL = "https://paper-api.alpaca.markets"

TICKER = "TSLA"
MAX_DOLLAR_RISK = 50.0
TIMEFRAME = "5m"

# Dummy web server to satisfy Render's port scanner
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"AI Trader is Live 24/7")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleServer)
    server.serve_forever()

def evaluate_and_trade():
    try:
        if API_KEY == "YOUR_ALPACA_KEY":
            print("[STATUS] Bot is running. (Add ALPACA_KEY in Environment to enable order execution)")
            return

        api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL, api_version='v2')
        positions = [p.symbol for p in api.list_positions()]
        if TICKER in positions:
            print(f"[{TICKER}] Position already open. Waiting.")
            return

        df = yf.download(TICKER, period="1d", interval=TIMEFRAME, progress=False)
        if len(df) < 4:
            return

        orb_high = float(df['High'].iloc[:3].max())
        orb_low = float(df['Low'].iloc[:3].min())
        latest_close = float(df['Close'].iloc[-1])

        if latest_close > orb_high:
            stop_price = round((orb_high + orb_low) / 2.0, 2)
            risk = latest_close - stop_price
            if risk <= 0:
                return
            shares = max(1, int(MAX_DOLLAR_RISK // risk))
            target_price = round(latest_close + (risk * 2.0), 2)

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
            print(f">>> [ORDER PLACED] {shares} {TICKER} @ {latest_close}")
    except Exception as e:
        print(f"Loop check: {e}")

if __name__ == "__main__":
    # Start the dummy web server thread for Render
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    print("AI Trader loop started...")
    while True:
        evaluate_and_trade()
        time.sleep(300)
        
