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

# --- TRACKING CONFIGURATION ---
SYMBOLS = [
    "frxEURUSD",  # EUR/USD
    "frxGBPUSD",  # GBP/USD
    "frxAUDUSD",  # AUD/USD
    "frxUSDJPY",  # USD/JPY
    "frxNZDUSD",  # NZD/USD
    "frxUSDCAD",  # USD/CAD
    "frxUSDCHF",  # USD/CHF
    "frxEURGBP"   # EUR/GBP
]

WINDOW_DURATION_SEC = 300  
CHECK_INTERVAL_SEC = 10    
MAX_LEN = WINDOW_DURATION_SEC // CHECK_INTERVAL_SEC  # 30 data points per pair

# --- DYNAMIC THRESHOLDS ---
FOREX_THRESHOLD = 0.0006  # 0.06% sensitivity for fiat pairs

# Keep track of when this virtual runner instance container launched
SCRIPT_START_TIME = time.time()

# Initialize separate rolling memory buffers for each asset pipeline
price_histories = {symbol: deque(maxlen=MAX_LEN) for symbol in SYMBOLS}
last_processed_times = {symbol: 0 for symbol in SYMBOLS}

def send_alert(msg):
    """Dispatches a real-time notification push to your Telegram channel"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        print(f"📱 Telegram alert sent successfully.", flush=True)
    except Exception as e:
        print(f"❌ Error sending Telegram alert: {e}", flush=True)

def trigger_next_runner():
    """Fires a GitHub REST API dispatch call using the absolute target filename"""
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
    """Runs in a background thread to enforce the 20-minute kill-switch safely."""
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
        print(f"📥 Message received from server type: {data.get('msg_type', 'unknown')}", flush=True)

        if "error" in data:
            print(f"⚠️ DERIV API ERROR: {data['error']['message']}", flush=True)
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
                
                display_name = f"{symbol[3:6]}/{symbol[6:]}"
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                current_threshold = FOREX_THRESHOLD
                price_format = f"{current_price:.5f}"
                    
                print(f"[{timestamp}] Live {display_name}: {price_format} | Buffer: {len(history)}/{MAX_LEN} | Trailing Move: {percent_change:+.4%}", flush=True)
                
                if len(history) >= 2:
                    if percent_change <= -current_threshold:
                        msg = f"📉 FLASH CRASH: {display_name} moved {percent_change:.2%} in the trailing window! (Price: {price_format})"
                        print(f"🚨 ALERT TRIGGERED: {msg}", flush=True)
                        send_alert(msg)
                        history.clear()
                    elif percent_change >= current_threshold:
                        print(f"ℹ️ Upward move detected ({percent_change:+.2%}), skipping notification.", flush=True)
                        history.clear()
    except Exception as e:
        print(f"❌ Error parsing incoming message: {e}", flush=True)

def on_error(ws, error):
    print(f"❌ WebSocket Error encountered: {error}", flush=True)

def on_close(ws, close_status_code, close_msg):
    print(f"🔌 WebSocket Connection Closed (Code: {close_status_code}, Msg: {close_msg}). Spawning next link...", flush=True)
    trigger_next_runner()

def on_open(ws):
    print(f"📡 WebSocket Handshake Successful! Initializing {len(SYMBOLS)} forex streams...", flush=True)
    for symbol in SYMBOLS:
        subscribe_msg = {"ticks": symbol, "subscribe": 1}
        ws.send(json.dumps(subscribe_msg))
        print(f"📤 Sent subscription request for asset: {symbol}", flush=True)
        time.sleep(0.2)

if __name__ == "__main__":
    print("🚀 TEXT CHECK VERIFICATION: Script execution started successfully!", flush=True)
    print("🚀 Booting real-time Forex WebSocket Volatility Scanner...", flush=True)
    
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
    
    print("🌐 Entering continuous event loop (run_forever)...", flush=True)
    ws.run_forever(ping_interval=10, ping_timeout=5)
        
