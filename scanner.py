# --- IMMEDIATE HARDCODED STARTUP PRINT ---
print("🔥 IMMEDIATE SCRIPT ENTRY: Python is reading the file!", flush=True)

import os
import json
import time
import requests
import threading
from collections import deque
import numpy as np

# Load Secure Credentials from GitHub Environment Variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
PERSONAL_ACCESS_TOKEN = os.environ.get("PERSONAL_ACCESS_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")

print("🔑 Environment variables loaded.", flush=True)

# Yahoo Finance Tickers for Major Forex Pairs
SYMBOLS = ["EURUSD=X", "GBPUSD=X", "AUDUSD=X", "USDJPY=X", "NZDUSD=X", "USDCAD=X", "USDCHF=X", "EURGBP=X"]

WINDOW_DURATION_SEC = 300  
CHECK_INTERVAL_SEC = 10    
MAX_LEN = WINDOW_DURATION_SEC // CHECK_INTERVAL_SEC  

FOREX_THRESHOLD = 0.0006  
SCRIPT_START_TIME = time.time()

# Rolling memory buffers for prices and calculated ATR values
price_histories = {symbol: deque(maxlen=MAX_LEN) for symbol in SYMBOLS}
atr_histories = {symbol: deque(maxlen=MAX_LEN) for symbol in SYMBOLS}

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

def detect_vertical_atr_spike(atr_history, min_jump_ratio=15.0):
    """Detects if the ATR has executed a vertical 'cliff' spike from a flat baseline."""
    if len(atr_history) < 10:
        return False
        
    atr_array = np.array(atr_history)
    baseline_min = np.min(atr_array[:-3]) # Look at the flat baseline period
    latest_atr = atr_array[-1]
    
    if baseline_min == 0:
        baseline_min = 0.00001
        
    expansion_ratio = latest_atr / baseline_min
    recent_slope = latest_atr - atr_array[-3]
    
    # Check if ATR multiplied rapidly and the jump is vertical
    if expansion_ratio >= min_jump_ratio and recent_slope > 0.0002:
        return True
        
    return False

def detect_vertical_price_crash(price_history):
    """Detects if price has dropped vertically like a cliff over the last few ticks."""
    if len(price_history) < 5:
        return False
        
    prices = list(price_history)
    # Measure drop from 4 periods ago to current
    drop_amount = prices[-5] - prices[-1]
    drop_pct = drop_amount / prices[-5]
    
    # If price plummeted by more than 0.08% sharply in a few ticks
    if drop_pct >= 0.0008:
        return True
        
    return False

def fetch_yahoo_prices():
    """Fetches live prices via Yahoo Finance public API endpoint and computes ATR volatility"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    while True:
        elapsed = time.time() - SCRIPT_START_TIME
        if elapsed >= 1200:
            print("⏰ 20 minutes elapsed. Closing loop...", flush=True)
            break

        for symbol in SYMBOLS:
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    result = data['chart']['result'][0]
                    
                    quotes = result['indicators']['quote'][0]
                    highs = quotes['high']
                    lows = quotes['low']
                    closes = quotes['close']
                    
                    valid_indices = [i for i, c in enumerate(closes) if c is not None]
                    if not valid_indices:
                        continue
                        
                    current_price = closes[valid_indices[-1]]
                    price_histories[symbol].append(current_price)
                    
                    if len(valid_indices) >= 2:
                        h = highs[valid_indices[-1]]
                        l = lows[valid_indices[-1]]
                        prev_c = closes[valid_indices[-2]]
                        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
                        atr_histories[symbol].append(tr)
                    
                    history = price_histories[symbol]
                    atr_buffer = atr_histories[symbol]
                    
                    if len(history) >= 2:
                        oldest_price = history[0]
                        percent_change = (current_price - oldest_price) / oldest_price
                        display_name = symbol.replace("=X", "")
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                        
                        print(f"[{timestamp}] Live {display_name}: {current_price:.5f} | Move: {percent_change:+.4%}", flush=True)
                        
                        # Check conditions
                        is_atr_cliff = detect_vertical_atr_spike(atr_buffer)
                        is_price_cliff = detect_vertical_price_crash(history)
                        
                        if percent_change <= -FOREX_THRESHOLD or is_atr_cliff or is_price_cliff:
                            if is_price_cliff:
                                crash_type = "📉 VERTICAL PRICE CRASH (CLIFF DROP DETECTED)"
                            elif is_atr_cliff:
                                crash_type = "⚡ VERTICAL ATR VOLATILITY SPIKE"
                            else:
                                crash_type = "📉 STANDARD THRESHOLD CRASH"
                                
                            msg = f"{crash_type}: {display_name} | Current Price: {current_price:.5f}"
                            print(f"🚨 ALERT: {msg}", flush=True)
                            send_alert(msg)
                            history.clear()
                            atr_buffer.clear()
            except Exception as e:
                print(f"⚠️ Error fetching {symbol}: {e}", flush=True)
            
            time.sleep(1)
        
        time.sleep(CHECK_INTERVAL_SEC)

if __name__ == "__main__":
    print("🚀 MAIN BLOCK REACHED: Vertical Crash & ATR Scanner active!", flush=True)
    fetch_yahoo_prices()
    print("🔌 Session Complete. Spawning next link...", flush=True)
    trigger_next_runner()
        
