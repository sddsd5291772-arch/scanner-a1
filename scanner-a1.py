import os
import json
import time
import requests
import websocket
from collections import deque

# Load Telegram credentials securely from GitHub Environment Variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Configuration for a 5-minute rolling window tracking every 10 seconds
WINDOW_DURATION_SEC = 300  
CHECK_INTERVAL_SEC = 10    
MAX_LEN = WINDOW_DURATION_SEC // CHECK_INTERVAL_SEC # 30 data points
THRESHOLD = 0.005  # 0.5% move

price_history = deque(maxlen=MAX_LEN)
last_processed_time = 0

def send_alert(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except Exception as e:
        print(f"❌ Error sending Telegram alert: {e}")

def on_message(ws, message):
    global last_processed_time
    data = json.loads(message)
    
    # Deriv pushes real-time stream ticks inside a 'tick' dictionary object
    if "tick" in data and "quote" in data["tick"]:
        current_time = time.time()
        
        # Throttle calculations to every 10 seconds to keep logging clean
        if current_time - last_processed_time >= CHECK_INTERVAL_SEC:
            last_processed_time = current_time
            current_price = float(data["tick"]["quote"])
            price_history.append(current_price)
            
            oldest_price = price_history[0]
            percent_change = (current_price - oldest_price) / oldest_price
            
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            print(f"[{timestamp}] Live EUR/USD (Deriv Stream): {current_price:.5f} | Buffer: {len(price_history)}/{MAX_LEN} | Trailing Move: {percent_change:+.4%}")
            
            if len(price_history) >= MAX_LEN:
                if abs(percent_change) >= THRESHOLD:
                    direction = "📈 UPWARD SPIKE" if percent_change > 0 else "📉 FLASH CRASH"
                    msg = f"{direction}: EUR/USD moved {percent_change:.2%} in the trailing 5 minutes! (Price: {current_price})"
                    print(f"🚨 ALERT TRIGGERED: {msg}")
                    send_alert(msg)
                    price_history.clear()

def on_error(ws, error):
    print(f"❌ WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("🔌 WebSocket Connection Closed")

def on_open(ws):
    print("📡 Connected to Deriv Public Cloud. Subscribing to EUR/USD feed...")
    # Handshake payload subscription signature for Deriv
    subscribe_msg = {
        "ticks": "frxEURUSD"
    }
    ws.send(json.dumps(subscribe_msg))

if __name__ == "__main__":
    print("🚀 Starting real-time EUR/USD WebSocket volatility scanner (Deriv Engine)...")
    
    # Open app route to Deriv's international system ecosystem endpoint (App ID 1 is the public playground)
    ws_url = "wss://ws.derivws.com/websockets/v3?app_id=1"
    
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    ws.run_forever(ping_interval=10, ping_timeout=5)
