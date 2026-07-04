import os
import time
import requests
from collections import deque

# Load secrets securely from GitHub Environment Variables
FINNHUB_TOKEN = os.environ.get("FINNHUB_TOKEN")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Configuration for a 5-minute rolling window tracking every 10 seconds
WINDOW_DURATION_SEC = 300  
CHECK_INTERVAL_SEC = 10    
MAX_LEN = WINDOW_DURATION_SEC // CHECK_INTERVAL_SEC
THRESHOLD = 0.005  # 0.5% move

price_history = deque(maxlen=MAX_LEN)

def get_live_price():
    try:
        # Corrected: Utilizing Finnhub's dedicated Forex Endpoint instead of /quote
        now = int(time.time())
        url = f"https://finnhub.io/api/v1/forex/candle"
        params = {
            "symbol": "OANDA:EUR_USD",
            "resolution": "1",
            "from": now - 3600,  # Lookback to ensure data coverage
            "to": now,
            "token": FINNHUB_TOKEN
        }
        
        response = requests.get(url, params=params).json()
        
        # Verify if a clean dataset array was sent back
        if "c" in response and len(response["c"]) > 0:
            return float(response["c"][-1])  # Pull the latest closed price tick
        else:
            print(f"⚠️ Empty/Unexpected Payload shape received: {response}")
            return None
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return None

def send_alert(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except Exception as e:
        print(f"❌ Error sending Telegram alert: {e}")

print("🚀 Starting real-time EUR/USD rolling volatility scanner...")

# Run loops dynamically within standard workflow execution time limits
start_time = time.time()
while time.time() - start_time < 1200:  # Run for ~20 minutes per execution session
    current_price = get_live_price()
    
    if current_price:
        price_history.append(current_price)
        
        # Track historical baseline information for calculation context
        oldest_price = price_history[0]
        percent_change = (current_price - oldest_price) / oldest_price
        
        # MONITORING LOGS: This prints directly to your GitHub Action console instantly
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        print(f"[{timestamp}] Live EUR/USD: {current_price:.5f} | Buffer Size: {len(price_history)}/{MAX_LEN} | Trailing Move: {percent_change:+.4%}")
        
        if len(price_history) >= MAX_LEN:
            if abs(percent_change) >= THRESHOLD:
                direction = "📈 UPWARD SPIKE" if percent_change > 0 else "📉 FLASH CRASH"
                message = f"{direction}: EUR/USD moved {percent_change:.2%} in the trailing 5 minutes! (Price: {current_price})"
                print(f"🚨 ALERT TRIGGERED: {message}")
                send_alert(message)
                price_history.clear() # Avoid duplicate alert spamming for the same continuous candle
                
    time.sleep(CHECK_INTERVAL_SEC)
