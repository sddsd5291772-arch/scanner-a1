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
# Define the major currency pairs you want to monitor concurrently
SYMBOLS = ["frxEURUSD", "frxGBPUSD", "frxAUDUSD", "frxUSDJPY"]

WINDOW_DURATION_SEC = 300  
CHECK_INTERVAL_SEC = 10    
MAX_LEN = WINDOW_DURATION_SEC // CHECK_INTERVAL_SEC # 30 data points per pair
THRESHOLD = 0.005  # 0.5% move

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
    data = json.loads(message)
    
    # Verify the incoming frame is a valid tick object
    if "tick" in data and "quote" in data["tick"] and "symbol" in data["tick"]:
        tick_data = data["tick"]
        symbol = tick_data["symbol"]
        
        # Guard rail: ignore symbols we didn't explicitly subscribe to
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
            
            # Clean symbol printer name (e.g., "frxEURUSD" -> "EUR/USD")
            display_name = f"{symbol[3:6]}/{symbol[6:]}"
            
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            print(f"[{timestamp}] Live {display_name}: {current_price:.5f} | Buffer: {len(history)}/{MAX_LEN} | Trailing Move: {percent_change:+.4%}")
            
            if len(history) >= MAX_LEN:
                if abs(percent_change) >= THRESHOLD:
                    direction = "📈 UPWARD SPIKE" if percent_change > 0 else "📉 FLASH CRASH"
                    msg = f"{direction}: {display_name} moved {percent_change:.2%} in the trailing 5 minutes! (Price: {current_price})"
                    print(f"🚨 ALERT TRIGGERED: {msg}")
                    send_alert(msg)
                    history.clear() # Avoid spamming alerts for the exact same wave

def on_error(ws, error):
    print(f"❌ WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("🔌 WebSocket Connection Closed Gracefully")

def on_open(ws):
    print(f"📡 Connected to Deriv Public Cloud. Initializing {len(SYMBOLS)} symbol pipelines...")
    
    # Loop over our symbol group and fire sequential subscription handshakes
    for symbol in SYMBOLS:
        subscribe_msg = {
            "ticks": symbol
        }
        ws.send(json.dumps(subscribe_msg))
        print(f"   ↳ Subscribed to: {symbol}")
        time.sleep(0.2) # Small pacing delay between requests

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
    
    # FIX: run_forever will now automatically break and close down the script
    # precisely after 20 minutes (1200 seconds), letting the next cron job take over!
    ws.run_forever(ping_interval=10, ping_timeout=5, timeout=1200)
