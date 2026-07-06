import os
import json
import time
import requests
import websocket
from collections import deque

# Load Telegram credentials securely from GitHub Environment Variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- TRACKING CONFIGURATION ---
SYMBOLS = ["frxEURUSD", "frxGBPUSD", "frxAUDUSD", "frxUSDJPY"]

WINDOW_DURATION_SEC = 300  
CHECK_INTERVAL_SEC = 10    
MAX_LEN = WINDOW_DURATION_SEC // CHECK_INTERVAL_SEC # 30 data points per pair
THRESHOLD = 0.005  # 0.5% move

# Track when this specific runner container session started
SCRIPT_START_TIME = time.time()

# Initialize a separate rolling memory buffer for each symbol dynamically
price_histories = {symbol: deque(maxlen=MAX_LEN) for symbol in SYMBOLS}
last_processed_times = {symbol: 0 for symbol in SYMBOLS}

def send_alert(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except Exception as e:
        print(f"❌ Error sending Telegram alert: {e}")

def on_message(ws, message):
    global SCRIPT_START_TIME
    data = json.loads(message)
    
    # Check if our 20-minute (1200 seconds) session runtime has expired
    if time.time() - SCRIPT_START_TIME >= 1200:
        print("⏰ 20 minutes elapsed for this runner session. Closing connection to hand off to next cron job...")
        ws.close()
        return

    # Verify the incoming frame is a valid tick object
    if "tick" in data and "quote" in data["tick"] and "symbol" in data["tick"]:
        tick_data = data["tick"]
        symbol = tick_data["symbol"]
        
        if symbol not in price_histories:
            return
            
        current_time = time.time()
        
        # Throttle parsing calculations independently per individual currency pair
        if current_time - last_processed_times[symbol] >= CHECK_INTERVAL_SEC:
            last_processed_times[symbol] = current_time
            current_price = float(tick_data["quote"])
            
            # Append to this specific symbol's vault pool
            price_histories[symbol].append(current_price)
            
            history = price_histories[symbol]
            oldest_price = history[0]
            percent_change = (current_price - oldest_price) / oldest_price
            
            display_name = f"{symbol[3:6]}/{symbol[6:]}"
            
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            print(f"[{timestamp}] Live {display_name}: {current_price:.5f} | Buffer: {len(history)}/{MAX_LEN} | Trailing Move: {percent_change:+.4%}")
            
            if len(history) >= MAX_LEN:
                if abs(percent_change) >= THRESHOLD:
                    direction = "📈 UPWARD SPIKE" if percent_change > 0 else "📉 FLASH CRASH"
                    msg = f"{direction}: {display_name} moved {percent_change:.2%} in the trailing 5 minutes! (Price: {current_price})"
                    print(f"🚨 ALERT TRIGGERED: {msg}")
                    send_alert(msg)
                    history.clear()

def on_error(ws, error):
    print(f"❌ WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("🔌 WebSocket Connection Closed Gracefully")

def on_open(ws):
    print(f"📡 Connected to Deriv Public Cloud. Initializing {len(SYMBOLS)} symbol pipelines...")
    
    for symbol in SYMBOLS:
        subscribe_msg = {
            "ticks": symbol
        }
        ws.send(json.dumps(subscribe_msg))
        print(f"   ↳ Subscribed to: {symbol}")
        time.sleep(0.2)

if __name__ == "__main__":
    print("🚀 Starting real-time Multi-Forex WebSocket Volatility Scanner...")
    
    ws_url = "wss://ws.derivws.com/websockets/v3?app_id=1"
    
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    # Removed the invalid timeout argument to resolve the crash error
    ws.run_forever(ping_interval=10, ping_timeout=5)
