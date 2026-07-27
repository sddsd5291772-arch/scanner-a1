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
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")

print("🔑 Environment variables loaded.", flush=True)

# Target currency pairs we want to find and track
TARGET_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "NZDUSD", "USDCAD", "USDCHF", "EURGBP"]
active_resolved_symbols = []

WINDOW_DURATION_SEC = 300  
CHECK_INTERVAL_SEC = 10    
MAX_LEN = WINDOW_DURATION_SEC // CHECK_INTERVAL_SEC  

FOREX_THRESHOLD = 0.0006  
SCRIPT_START_TIME = time.time()

price_histories = {}
last_processed_times = {}

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

def timeout_checker(ws):
    print("⏱️ Background timeout watcher thread initialized.", flush=True)
    while True:
        if time.time() - SCRIPT_START_TIME >= 1200:
            print("⏰ 20 minutes elapsed. Closing connection...", flush=True)
            ws.close()
            break
        time.sleep(10)

def on_message(ws, message):
    global active_resolved_symbols
    try:
        data = json.loads(message)
        msg_type = data.get("msg_type")

        # Step 1: Handle active symbols lookup response
        if msg_type == "active_symbols":
            symbols_data = data.get("active_symbols", [])
            print(f"🔍 Received {len(symbols_data)} total assets from Deriv. Filtering for targets...", flush=True)
            
            for item in symbols_data:
                symbol_code = item.get("symbol")
                display_name = item.get("display_name", "")
                
                # Match target pairs dynamically against Deriv's internal symbol database
                for target in TARGET_PAIRS:
                    if target in symbol_code.upper():
                        if symbol_code not in active_resolved_symbols:
                            active_resolved_symbols.append(symbol_code)
                            price_histories[symbol_code] = deque(maxlen=MAX_LEN)
                            last_processed_times[symbol_code] = 0
                            
                            # Subscribe immediately to the valid discovered symbol code
                            sub_payload = {"ticks": symbol_code, "subscribe": 1}
                            ws.send(json.dumps(sub_payload))
                            print(f"✅ Subscribed to verified symbol: {symbol_code} ({display_name})", flush=True)
            return

        # Step 2: Handle live price ticks
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
                
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                print(f"[{timestamp}] Live {symbol}: {current_price:.5f} | Buffer: {len(history)}/{MAX_LEN} | Move: {percent_change:+.4%}", flush=True)

        if "error" in data:
            print(f"⚠️ API Error: {data['error'].get('message')}", flush=True)

    except Exception as e:
        print(f"❌ Error parsing message: {e}", flush=True)

def on_error(ws, error):
    print(f"❌ WebSocket Error: {error}", flush=True)

def on_close(ws, close_status_code, close_msg):
    print(f"🔌 Connection Closed. Spawning next link...", flush=True)
    trigger_next_runner()

def on_open(ws):
    print(f"📡 WebSocket Handshake Successful! Requesting active symbol catalog...", flush=True)
    # Request Deriv's full active symbol list to automatically find correct naming structures
    active_symbols_request = {
        "active_symbols": "brief",
        "product_type": "basic"
    }
    ws.send(json.dumps(active_symbols_request))

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
    
