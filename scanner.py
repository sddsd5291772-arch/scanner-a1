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

# Direct universal major forex symbols used on Deriv websockets
SYMBOLS = ["frxEURUSD", "frxGBPUSD", "frxAUDUSD", "frxUSDJPY", "frxNZDUSD", "frxUSDCAD", "frxUSDCHF", "frxEURGBP"]

WINDOW_DURATION_SEC = 300  
CHECK_INTERVAL_SEC = 10    
MAX_LEN = WINDOW_DURATION_SEC // CHECK_INTERVAL_SEC  

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
    try:
        data = json.loads(message)
        
        if "error" in data:
            print(f"⚠️ API Error for {data.get('echo_req', {})}: {data['error'].get('message')}", flush=True)
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
                
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                print(f"[{timestamp}] Live {symbol}: {current_price:.5f} | Buffer: {len(history)}/{MAX_LEN} | Move: {percent_change:+.4%}", flush=True)

    except Exception as e:
        print(f"❌ Error parsing message: {e}", flush=True)

def on_error(ws, error):
    print(f"❌ WebSocket Error: {error}", flush=True)

def on_close(ws, close_status_code, close_msg):
    print(f"🔌 Connection Closed. Spawning next link...", flush=True)
    trigger_next_runner()

def on_open(ws):
    print(f"📡 WebSocket Handshake Successful! Subscribing directly to symbols...", flush=True)
    for symbol in SYMBOLS:
        sub_payload = {"ticks": symbol, "subscribe": 1}
        ws.send(json.dumps(sub_payload))
        print(f"📤 Sent subscription for: {symbol}", flush=True)
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
    
