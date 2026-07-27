# --- IMMEDIATE HARDCODED STARTUP PRINT ---
print("🔥 IMMEDIATE SCRIPT ENTRY: Python is reading the file!", flush=True)

import os
import json
import time
import requests
import threading
from collections import deque

# Load Secure Credentials from GitHub Environment Variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
PERSONAL_ACCESS_TOKEN = os.environ.get("PERSONAL_ACCESS_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")

print("🔑 Environment variables loaded.", flush=True)

# Yahoo Finance Tickers for Major Forex Pairs
SYMBOLS = ["EURUSD=X", "GBPUSD=X", "AUDUSD=X", "USDJPY=X", "NZDUSD=X", "USDCAD=X", "USDCHF=X", "EURGBP=X"]

WINDOW_DURATION_SEC = 300  
CHECK_INTERVAL_SEC = 10    
MAX_LEN = WINDOW_DURATION_SEC // CHECK_INTERVAL_SEC  

FOREX_THRESHOLD = 0.0006  
SCRIPT_START_TIME = time.time()

price_histories = {symbol: deque(maxlen=MAX_LEN) for symbol in SYMBOLS}

def send_alert(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        print(f"📱 Telegram alert sent successfully.", flush=True)
    except Exception as e:
        print(f"❌ Error sending Telegram alert: {e}", flush=True)

def trigger_next_runner():
    if not PERSONAL_ACCESS_TOKEN or not GITHUB_REPOSITORY:
        print("⚠️ Missing tokens. Chain broken.", flush=True)
        return

    filename = "run-scanner.yml"
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/workflows/{filename}/dispatches"
    headers = {
        "Authorization": f"token {PERSONAL_ACCESS_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    try:
        response = requests.post(url, headers=headers, json={"ref": "main"})
        if response.status_code in [200, 204]:
            print("✅ Next workflow dispatched successfully.", flush=True)
        else:
            print(f"❌ Dispatch rejected: {response.text}", flush=True)
    except Exception as e:
        print(f"❌ Network issue dispatching next link: {e}", flush=True)

def fetch_yahoo_prices():
    """Fetches live prices via Yahoo Finance public API endpoint"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    while True:
        elapsed = time.time() - SCRIPT_START_TIME
        if elapsed >= 1200:
            print("⏰ 20 minutes elapsed. Closing loop...", flush=True)
            break

        for symbol in SYMBOLS:
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    result = data['chart']['result'][0]
                    current_price = result['meta']['regularMarketPrice']
                    
                    price_histories[symbol].append(current_price)
                    history = price_histories[symbol]
                    
                    if len(history) >= 2:
                        oldest_price = history[0]
                        percent_change = (current_price - oldest_price) / oldest_price
                        display_name = symbol.replace("=X", "")
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                        
                        print(f"[{timestamp}] Live {display_name}: {current_price:.5f} | Buffer: {len(history)}/{MAX_LEN} | Move: {percent_change:+.4%}", flush=True)
                        
                        if percent_change <= -FOREX_THRESHOLD:
                            msg = f"📉 FLASH CRASH: {display_name} moved {percent_change:.2%}! (Price: {current_price:.5f})"
                            print(f"🚨 ALERT: {msg}", flush=True)
                            send_alert(msg)
                            history.clear()
            except Exception as e:
                print(f"⚠️ Error fetching {symbol}: {e}", flush=True)
            
            time.sleep(1)
        
        time.sleep(CHECK_INTERVAL_SEC)

if __name__ == "__main__":
    print("🚀 MAIN BLOCK REACHED: Yahoo Finance Scanner active!", flush=True)
    
    # Run the price polling loop
    fetch_yahoo_prices()
    
    print("🔌 Session Complete. Spawning next link...", flush=True)
    trigger_next_runner()
    
