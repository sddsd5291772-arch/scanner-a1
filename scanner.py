# --- IMMEDIATE HARDCODED STARTUP PRINT ---
print("🔥 IMMEDIATE SCRIPT ENTRY: Python is reading the file!", flush=True)

import os
import json
import time
import requests
import websocket
import threading
from collections import deque

# Load Secure Credentials from GitHub Environment Variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
PERSONAL_ACCESS_TOKEN = os.environ.get("PERSONAL_ACCESS_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")  # Set automatically by GitHub

print("🔑 Environment variables loaded.", flush=True)

# --- TRACKING CONFIGURATION (Corrected Deriv Symbol Format) ---
SYMBOLS = [
    "frxEURUSD",  # Keeping fallback options or standard formats
    "frxGBPUSD",
    "frxAUDUSD",
    "frxUSDJPY",
    "frxNZDUSD",
    "frxUSDCAD",
    "frxUSDCHF",
    "frxEURGBP"
]

WINDOW_DURATION_SEC = 300  
CHECK_INTERVAL_SEC = 10    
MAX_LEN = WINDOW_DURATION_SEC // CHECK_INTERVAL_SEC  

# --- DYNAMIC THRESHOLDS ---
FOREX_THRESHOLD = 0.0006  

SCRIPT_START_TIME = time.time()

price_histories = {symbol: deque(maxlen=MAX_LEN) for symbol in SYMBOLS}
last_processed_times = {symbol: 0 for symbol in SYMBOLS}

def send_alert(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        print(f"📱 Telegram alert sent successfully.", flush=True)
    except Exception as e:
        print(f"❌ Error sending Telegram alert: {e}", flush=True)

def trigger_next_runner():
    if not PERSONAL_ACCESS_TOKEN or not GITHUB_REPOSITORY:
        print("⚠️ Missing environment tokens. Continuous loop chain broken.", flush=True)
        return

    filename = "run-scanner.yml"
    print(f"⛓️ Chain-triggering target path file: '{filename}'...", flush=True)
    
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/workflows/{filename}/dispatches"
    headers = {
        "Authorization": f"token {PERSONAL_ACCESS_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {"ref": "main"}

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code in [200, 204]:
            print("✅ Success! The next workflow link has been dispatched successfully.", flush=True)
        else:
            print(f"❌ API Rejected execution dispatch request (Status {response.status_code}): {response.text}", flush=True)
    except Exception as e:
        print(f"❌ Network issue dispatching next link: {e}", flush=True)

def timeout_checker(ws):
    print("⏱️ Background timeout watcher thread initialized.", flush=True)
    while True:
        elapsed = time.time() - SCRIPT_START_TIME
        if elapsed >= 1200:
            print(f"⏰ 20 minutes ({elapsed:.1f}s) elapsed for this runner session. Closing connection...", flush=True)
            ws.close()
            break
        time.sleep(10)

def on_message(ws, message):
    try:
        data = json.loads(message)
        print(f"📥 RAW Message: {data}", flush=True)

        if "error" in data:
            print(f"⚠️ DERIV API ERROR on symbol: {data['error'].get('details', {})}", flush=True)
            return

        if "tick" in data and "quote" in data["tick"] and "symbol" in data["tick"]:
            tick_data = data["tick"]
            symbol = tick_data["symbol"]
            
            if symbol not in price_histories:
                return
                
            current_time = time.time()
            
            if current_time - last_processed_times[symbol] >= CHECK_INTERVAL_SEC:
                last_processed_times[symbol] = current_time
                current_price = float(tick_data["quote"])
                price_histories[symbol].append(current_price)
                
                history = price_histories[symbol]
                oldest_price = history[0]
                percent_change = (current_price - oldest_price) / oldest_price
                
                display_name = symbol
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                price_format = f"{current_price:.5f}"
                    
                print(f"[{timestamp}] Live {display_name}: {price_format} | Buffer: {len(history)}/{MAX_LEN} | Trailing Move: {percent_change:+.4%}", flush=True)
    except Exception as e:
        print(f"❌ Error parsing incoming message: {e}", flush=True)

def on_error(ws, error):
    print(f"❌ WebSocket Error encountered: {error}", flush=True)

def on_close(ws, close_status_code, close_msg):
    print(f"🔌 WebSocket Connection Closed. Spawning next link...", flush=True)
    trigger_next_runner()

def on_open(ws):
    print(f"📡 WebSocket Handshake Successful! Initializing streams...", flush=True)
    # Trying alternative symbol mappings if 'frx' fails, let's query raw symbols or active symbols
    alt_symbols = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "NZDUSD", "USDCAD", "USDCHF", "EURGBP"]
    for symbol in alt_symbols:
        subscribe_msg = {"ticks": symbol, "subscribe": 1}
        ws.send(json.dumps(subscribe_msg))
        print(f"📤 Sent subscription request for asset: {symbol}", flush=True)
        time.sleep(0.2)

if __name__ == "__main__":
    print("🚀 MAIN BLOCK REACHED: Script execution is fully active!", flush=True)
    ws_url = "wss://ws.derivws.com/websockets/v3?app_id=1089"
    
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    timer_thread = threading.Thread(target=timeout_checker, args=(ws,))
    timer_thread.daemon = True
    timer_thread.start()
    
    ws.run_forever(ping_interval=10, ping_timeout=5)
    
