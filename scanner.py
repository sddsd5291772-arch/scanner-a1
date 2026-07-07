import os
import json
import time
import requests
import websocket
from collections import deque

# Load Secure Credentials from GitHub Environment Variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
PERSONAL_ACCESS_TOKEN = os.environ.get("PERSONAL_ACCESS_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")  # Set automatically by GitHub

# --- TRACKING CONFIGURATION ---
SYMBOLS = ["frxEURUSD", "frxGBPUSD", "frxAUDUSD", "frxUSDJPY"]

WINDOW_DURATION_SEC = 300  
CHECK_INTERVAL_SEC = 10    
MAX_LEN = WINDOW_DURATION_SEC // CHECK_INTERVAL_SEC  # 30 data points per pair

# Change this to 0.0010 to catch real 10-pip drops, or keep 0.0001 for hyper-sensitive testing
THRESHOLD = 0.0010  

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
    except Exception as e:
        print(f"❌ Error sending Telegram alert: {e}")

def trigger_next_runner():
    """Fires a GitHub REST API dispatch call using the absolute target filename"""
    if not PERSONAL_ACCESS_TOKEN or not GITHUB_REPOSITORY:
        print("⚠️ Missing environment tokens. Continuous loop chain broken.")
        return

    filename = "run-scanner.yml"
    print(f"⛓️ Chain-triggering target path file: '{filename}'...")
    
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/workflows/{filename}/dispatches"
    
    headers = {
        "Authorization": f"token {PERSONAL_ACCESS_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {"ref": "main"}

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code in [200, 204]:
            print("✅ Success! The next workflow link has been dispatched successfully.")
        else:
            print(f"❌ API Rejected execution dispatch request (Status {response.status_code}): {response.text}")
    except Exception as e:
        print(f"❌ Network issue dispatching next link: {e}")

def on_message(ws, message):
    global SCRIPT_START_TIME
    data = json.loads(message)
    
    # Check if our 20-minute (1200 seconds) operational execution cycle is complete
    if time.time() - SCRIPT_START_TIME >= 1200:
        print("⏰ 20 minutes elapsed for this runner session. Closing connection to trigger next runner in on_close...")
        ws.close()
        return

    # Process incoming tick frames cleanly
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
            print(f"[{timestamp}] Live {display_name}: {current_price:.5f} | Buffer: {len(history)}/{MAX_LEN} | Trailing Move: {percent_change:+.4%}")
            
            if len(history) >= 2:
                # Only trigger if percent_change is negative and breaches the downward threshold
                if percent_change <= -THRESHOLD:
                    msg = f"📉 FLASH CRASH: {display_name} moved {percent_change:.2%} in the trailing window! (Price: {current_price})"
                    print(f"🚨 ALERT TRIGGERED: {msg}")
                    send_alert(msg)
                    history.clear()
                # Clear out positive spikes silently without hitting Telegram
                elif percent_change >= THRESHOLD:
                    print(f"ℹ️ Upward move detected ({percent_change:+.2%}), skipping notification.")
                    history.clear()

def on_error(ws, error):
    print(f"❌ WebSocket Error encountered: {error}")

def on_close(ws, close_status_code, close_msg):
    print("🔌 WebSocket Connection Closed. Spawning next link in the chain to keep monitoring alive...")
    trigger_next_runner()

def on_open(ws):
    print(f"📡 Connected to Deriv Public Cloud. Initializing {len(SYMBOLS)} symbol data streams...")
    for symbol in SYMBOLS:
        subscribe_msg = {"ticks": symbol}
        ws.send(json.dumps(subscribe_msg))
        time.sleep(0.2)

if __name__ == "__main__":
    print("🚀 Booting real-time Multi-Forex WebSocket Volatility Scanner...")
    ws_url = "wss://ws.derivws.com/websockets/v3?app_id=1"
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever(ping_interval=10, ping_timeout=5)
