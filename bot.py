import os
import time
import json
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import yfinance as yf

# Alpaca modern SDK
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

# 1. API Credentials (Alpaca Paper Trading)
API_KEY = os.getenv("ALPACA_KEY", "YOUR_ALPACA_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET", "YOUR_ALPACA_SECRET")

TICKER = "TSLA"
MAX_DOLLAR_RISK = 50.0  # Risk per trade
TIMEFRAME = "5m"

# In-memory journal & bot status for the live web UI
bot_state = {
    "status": "Scanning Active",
    "last_scan_time": "Initializing...",
    "ticker": TICKER,
    "current_price": 0.0,
    "orb_high": 0.0,
    "orb_low": 0.0,
    "journal": [
        {
            "time": datetime.now().strftime("%I:%M %p"),
            "event": "System Started",
            "type": "INFO",
            "explanation": "Autonomous AI Trader active on Render. Awaiting US market open (7:00 PM IST / 9:30 AM ET) to establish the 15-minute Opening Range."
        }
    ]
}

def add_journal_entry(event, entry_type, explanation):
    timestamp = datetime.now().strftime("%I:%M %p")
    bot_state["journal"].insert(0, {
        "time": timestamp,
        "event": event,
        "type": entry_type,
        "explanation": explanation
    })
    if len(bot_state["journal"]) > 20:
        bot_state["journal"].pop()

# --- WEB DASHBOARD SERVER (Satisfies Render Free Tier) ---
class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/data":
            account_data = {"equity": 100000.0, "cash": 100000.0, "pnl": 0.0, "positions": []}
            if API_KEY != "YOUR_ALPACA_KEY":
                try:
                    trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
                    acct = trading_client.get_account()
                    positions = trading_client.get_all_positions()
                    account_data["equity"] = round(float(acct.equity), 2)
                    account_data["cash"] = round(float(acct.cash), 2)
                    account_data["pnl"] = round(float(acct.equity) - 100000.0, 2)
                    account_data["positions"] = [
                        {
                            "symbol": p.symbol,
                            "qty": p.qty,
                            "current_price": p.current_price,
                            "unrealized_pl": p.unrealized_pl,
                            "side": str(p.side)
                        } for p in positions
                    ]
                except Exception as e:
                    print(f"API Fetch Error: {e}")

            payload = {"bot": bot_state, "account": account_data}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        # HTML Mobile-Optimized Dashboard
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()

        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>AI Trader Journal</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <style>
                body {{ background-color: #0B0E14; color: #E2E8F0; font-family: sans-serif; }}
                .font-mono {{ font-family: monospace; }}
            </style>
        </head>
        <body class="p-4 md:p-8 max-w-3xl mx-auto">
            <!-- Header -->
            <div class="flex items-center justify-between pb-4 border-b border-gray-800">
                <div>
                    <h1 class="text-xl font-bold flex items-center gap-2">
                        <span class="w-3 h-3 bg-emerald-500 rounded-full animate-pulse"></span>
                        AI Day Trader Dashboard
                    </h1>
                    <p class="text-xs text-gray-400 mt-0.5">Asset: <span class="text-white font-bold">{TICKER}</span> (15m ORB Engine)</p>
                </div>
                <span class="px-2.5 py-1 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded text-xs font-mono font-bold">ONLINE</span>
            </div>

            <!-- Stats Bar -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3 my-5">
                <div class="bg-gray-900 border border-gray-800 rounded-xl p-3">
                    <span class="text-[11px] text-gray-400 uppercase">Equity</span>
                    <p id="equity-val" class="text-lg font-bold font-mono text-white mt-1">$100,000.00</p>
                </div>
                <div class="bg-gray-900 border border-gray-800 rounded-xl p-3">
                    <span class="text-[11px] text-gray-400 uppercase">Net PnL</span>
                    <p id="pnl-val" class="text-lg font-bold font-mono text-emerald-400 mt-1">+$0.00</p>
                </div>
                <div class="bg-gray-900 border border-gray-800 rounded-xl p-3">
                    <span class="text-[11px] text-gray-400 uppercase">Risk / Trade</span>
                    <p class="text-lg font-bold font-mono text-amber-400 mt-1">${MAX_DOLLAR_RISK:.2f}</p>
                </div>
                <div class="bg-gray-900 border border-gray-800 rounded-xl p-3">
                    <span class="text-[11px] text-gray-400 uppercase">State</span>
                    <p id="engine-status" class="text-xs font-bold font-mono text-blue-400 mt-2 truncate">Scanning</p>
                </div>
            </div>

            <!-- 15m Range Monitor -->
            <div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-5">
                <div class="flex justify-between items-center mb-2">
                    <span class="text-xs font-semibold uppercase text-gray-400">15-Min Opening Range</span>
                    <span id="last-scan" class="text-[11px] text-gray-500 font-mono">--</span>
                </div>
                <div class="grid grid-cols-3 gap-2 text-center">
                    <div class="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                        <span class="text-[10px] text-gray-400 uppercase">ORB High (Buy)</span>
                        <p id="orb-high" class="text-sm font-bold font-mono text-emerald-400 mt-1">$0.00</p>
                    </div>
                    <div class="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                        <span class="text-[10px] text-gray-400 uppercase">Latest Close</span>
                        <p id="curr-price" class="text-sm font-bold font-mono text-white mt-1">$0.00</p>
                    </div>
                    <div class="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                        <span class="text-[10px] text-gray-400 uppercase">ORB Low (Stop)</span>
                        <p id="orb-low" class="text-sm font-bold font-mono text-rose-400 mt-1">$0.00</p>
                    </div>
                </div>
            </div>

            <!-- Human AI Journal -->
            <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
                <h2 class="text-sm font-bold text-white mb-1">📖 AI Trade Journal & Decision Log</h2>
                <p class="text-xs text-gray-400 mb-3">Live reasoning behind every trade decision.</p>
                <div id="journal-list" class="space-y-2.5"></div>
            </div>

            <script>
                async function updateUI() {{
                    try {{
                        const res = await fetch('/api/data');
                        const data = await res.json();

                        document.getElementById('equity-val').innerText = '$' + data.account.equity.toLocaleString();
                        const pnl = data.account.pnl;
                        const pnlEl = document.getElementById('pnl-val');
                        pnlEl.innerText = (pnl >= 0 ? '+$' : '-$') + Math.abs(pnl).toFixed(2);
                        pnlEl.className = 'text-lg font-bold font-mono mt-1 ' + (pnl >= 0 ? 'text-emerald-400' : 'text-rose-400');

                        document.getElementById('engine-status').innerText = data.bot.status;
                        document.getElementById('last-scan').innerText = data.bot.last_scan_time;
                        document.getElementById('orb-high').innerText = '$' + data.bot.orb_high.toFixed(2);
                        document.getElementById('orb-low').innerText = '$' + data.bot.orb_low.toFixed(2);
                        document.getElementById('curr-price').innerText = '$' + data.bot.current_price.toFixed(2);

                        const list = document.getElementById('journal-list');
                        list.innerHTML = '';
                        data.bot.journal.forEach(item => {{
                            const card = document.createElement('div');
                            card.className = 'bg-gray-950 border border-gray-800 rounded-lg p-3 text-xs';
                            let badge = 'bg-blue-950 text-blue-400 border-blue-800';
                            if (item.type === 'EXECUTE') badge = 'bg-emerald-950 text-emerald-400 border-emerald-800';
                            if (item.type === 'WARN') badge = 'bg-amber-950 text-amber-400 border-amber-800';
                            if (item.type === 'WAIT') badge = 'bg-gray-800 text-gray-300 border-gray-700';

                            card.innerHTML = `
                                <div class="flex items-center justify-between mb-1">
                                    <div class="flex items-center gap-1.5">
                                        <span class="px-1.5 py-0.5 border rounded text-[9px] font-mono font-bold ${{badge}}">${{item.type}}</span>
                                        <span class="font-semibold text-white">${{item.event}}</span>
                                    </div>
                                    <span class="text-gray-500 font-mono text-[10px]">${{item.time}}</span>
                                </div>
                                <p class="text-gray-300 leading-normal">${{item.explanation}}</p>
                            `;
                            list.appendChild(card);
                        }});
                    }} catch (e) {{ console.error(e); }}
                }}
                setInterval(updateUI, 10000);
                updateUI();
            </script>
        </body>
        </html>
        """
        self.wfile.write(html.encode("utf-8"))

def start_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    server.serve_forever()

# --- AUTONOMOUS TRADING ENGINE ---
def run_trading_scan():
    try:
        now_time = datetime.now().strftime("%I:%M:%S %p")
        bot_state["last_scan_time"] = now_time

        if API_KEY == "YOUR_ALPACA_KEY":
            bot_state["status"] = "Keys Missing"
            add_journal_entry("API Keys Needed", "WARN", "Add ALPACA_KEY and ALPACA_SECRET in Render Environment variables.")
            return

        trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
        clock = trading_client.get_clock()

        if not clock.is_open:
            bot_state["status"] = "Market Closed"
            add_journal_entry("Market Closed", "WAIT", f"US Market is closed. Opens at {clock.next_open.strftime('%I:%M %p ET')} (7:00 PM IST). Standing by.")
            return

        positions = [p.symbol for p in trading_client.get_all_positions()]
        if TICKER in positions:
            bot_state["status"] = f"In Position ({TICKER})"
            return

        df = yf.download(TICKER, period="1d", interval=TIMEFRAME, progress=False)
        if len(df) < 4:
            bot_state["status"] = "Forming ORB"
            add_journal_entry("Forming 15m Range", "WAIT", f"Waiting for the first three 5-min bars to lock the opening range for {TICKER}.")
            return

        orb_high = float(df['High'].iloc[:3].max())
        orb_low = float(df['Low'].iloc[:3].min())
        latest_close = float(df['Close'].iloc[-1])

        bot_state["orb_high"] = orb_high
        bot_state["orb_low"] = orb_low
        bot_state["current_price"] = latest_close

        if latest_close > orb_high:
            stop_price = round((orb_high + orb_low) / 2.0, 2)
            risk = latest_close - stop_price
            if risk <= 0:
                return

            shares = max(1, int(MAX_DOLLAR_RISK // risk))
            target_price = round(latest_close + (risk * 2.0), 2)

            # Bracket order with Stop Loss and Take Profit
            order_data = MarketOrderRequest(
                symbol=TICKER,
                qty=shares,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=target_price),
                stop_loss=StopLossRequest(stop_price=stop_price)
            )
            trading_client.submit_order(order_data=order_data)

            bot_state["status"] = f"Bought {shares} {TICKER}"
            add_journal_entry(
                f"BUY {shares} {TICKER}",
                "EXECUTE",
                f"5-min candle closed above ORB High (${orb_high:.2f}). Sized {shares} shares for ${MAX_DOLLAR_RISK:.2f} max risk. Stop at ${stop_price:.2f}, Target at ${target_price:.2f}."
            )
        else:
            bot_state["status"] = "Scanning"
            add_journal_entry(f"Scanned {TICKER}", "WAIT", f"Current price ${latest_close:.2f} is below breakout level (${orb_high:.2f}). Will check again in 5 minutes.")

    except Exception as e:
        print(f"Scan loop error: {e}")

if __name__ == "__main__":
    # Start web dashboard thread
    threading.Thread(target=start_server, daemon=True).start()

    print("AI Trader with Journal UI active...")
    while True:
        run_trading_scan()
        time.sleep(300)
        
