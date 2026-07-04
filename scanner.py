import os
import time
import requests
from collections import deque

# Load secrets from GitHub Environment Variables
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
        url = f"https://finnhub.io/api/v1/quote?symbol=OANDA:EUR_USD&token={FINNHUB_TOKEN}"
        res = requests.get(url).json()
        return float(res['c'])
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
        
        # MONITORING LOGS: This prints to your GitHub Action console every 10 seconds
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        print(f"[{timestamp}] Live Price: {current_price:.5f} | 5-Min Window Size: {len(price_history)}/{MAX_LEN} | 5-Min Move: {percent_change:+.4%}")
        
        if len(price_history) >= MAX_LEN:
            if abs(percent_change) >= THRESHOLD:
                direction = "📈 UPWARD SPIKE" if percent_change > 0 else "📉 FLASH CRASH"
                message = f"{direction}: EUR/USD moved {percent_change:.2%} in the trailing 5 minutes! (Price: {current_price})"
                print(f"🚨 ALERT TRIGGERED: {message}")
                send_alert(message)
                price_history.clear() # Avoid alert spamming for the same continuous spike
                
    time.sleep(CHECK_INTERVAL_SEC)
