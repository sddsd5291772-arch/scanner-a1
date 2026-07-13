import os
import json
import time
import requests
import websocket
import yfinance as yf
import numpy as np
from collections import deque

# Load Secure Credentials from GitHub Environment Variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
PERSONAL_ACCESS_TOKEN = os.environ.get("PERSONAL_ACCESS_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")

# --- TRACKING CONFIGURATION ---
SYMBOLS = [
    "frxEURUSD", "frxGBPUSD", "frxAUDUSD", "frxUSDJPY",
    "frxNZDUSD", "frxUSDCAD", "frxUSDCHF", "frxEURGBP",
    "cryBTCUSD", "cryXMRUSD"
]

YFINANCE_MAPPING = {
    "frxEURUSD": "EURUSD=X", "frxGBPUSD": "GBPUSD=X", "frxAUDUSD": "AUDUSD=X",
    "frxUSDJPY": "JPY=X",    "frxNZDUSD": "NZDUSD=X", "frxUSDCAD": "USDCAD=X",
    "frxUSDCHF": "CHF=X",    "frxEURGBP": "EURGBP=X",
    "cryBTCUSD": "BTC-USD",  "cryXMRUSD": "XMR-USD"
}

WINDOW_DURATION_SEC = 300  
CHECK_INTERVAL_SEC = 10    
MAX_LEN = WINDOW_DURATION_SEC // CHECK_INTERVAL_SEC  

# --- BASE SENSITIVITY ---
FOREX_THRESHOLD = 0.0006  
BTC_THRESHOLD   = 0.0050  
XMR_THRESHOLD   = 0.0075  
HEATMAP_BUFFER_PERCENT = 0.00005  # 0.0010 = 0.10% buffer away from the floor. Lower this to get tighter to the bottom.

# Dictionaries to hold heatmap calculations and state tracking
DYNAMIC_LIQUIDITY_FLOORS = {}
LAST_ZONE_ALERT_TIME = {symbol: 0 for symbol in SYMBOLS} # 10-minute alert cooldown

def calculate_heatmap_floors():
    """Fetches free historical weekly data with volume and calculates the BigBeluga floor"""
    print("🔮 Fetching free historical market depth to build volume heatmaps...")
    for deriv_symbol, yf_ticker in YFINANCE_MAPPING.items():
        try:
            ticker = yf.Ticker(yf_ticker)
            df = ticker.history(period="2y", interval="1wk")
            
            if df.empty or len(df) < 100:
                continue
                
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            ranges = np.max([high_low, high_close, low_close], axis=0)
            atr_100 = np.mean(ranges[-100:])
            
            bin_size = atr_100 * 0.25
            
            recent_data = df.tail(40) 
            v_max = recent_data['High'].max()
            v_min = recent_data['Low'].min()
            total_range = v_max - v_min
            
            num_bins = min(40, int(np.floor(total_range / bin_size)))
            if num_bins < 10: num_bins = 10
            
            bin_edges = np.linspace(v_min, v_max, num_bins + 1)
            volume_bins = np.zeros(num_bins)
            
            for _, bar in recent_data.iterrows():
                mid_price = bar['Close']
                for idx in range(num_bins):
                    if bin_edges[idx] <= mid_price <= bin_edges[idx+1]:
                        volume_bins[idx] += bar['Volume'] if bar['Volume'] > 0 else 1
            
            max_volume_idx = np.argmax(volume_bins)
            highest_liquidity_floor = bin_edges[max_volume_idx]
            
            DYNAMIC_LIQUIDITY_FLOORS[deriv_symbol] = highest_liquidity_floor
            print(f"   ✅ {deriv_symbol[3:]} Heatmap Floor calculated: {highest_liquidity_floor:.5f}")
            
        except Exception as e:
            print(f"   ❌ Failed calculating heatmap layer for {deriv_symbol}: {e}")

def send_alert(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except Exception as e:
        print(f"❌ Error sending Telegram alert: {e}")

def trigger_next_runner():
    if not PERSONAL_ACCESS_TOKEN or not GITHUB_REPOSITORY:
        print("⚠️ Missing environment tokens. Continuous loop chain broken.")
        return
    filename = "run-scanner.yml"
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/workflows/{filename}/dispatches"
    headers = {"Authorization": f"token {PERSONAL_ACCESS_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        response = requests.post(url, headers=headers, json={"ref": "main"})
        if response.status_code in [200, 204]:
            print("✅ Next link workflow dispatched successfully.")
    except Exception as e:
        print(f"❌ Dispatch exception: {e}")

def on_message(ws, message):
    data = json.loads(message)
    
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
            
            # Threshold Routing
            if "XMR" in display_name:
                current_threshold = XMR_THRESHOLD
            elif "BTC" in display_name:
                current_threshold = BTC_THRESHOLD
            else:
                current_threshold = FOREX_THRESHOLD
            
            price_format = f"{current_price:.2f}" if ("BTC" in display_name or "XMR" in display_name) else f"{current_price:.5f}"
            
            heatmap_floor = DYNAMIC_LIQUIDITY_FLOORS.get(symbol, 0.0)
            floor_status = f"Floor: {heatmap_floor:.2f}" if "BTC" in display_name else f"Floor: {heatmap_floor:.5f}"
            
            print(f"[{timestamp}] Live {display_name}: {price_format} | Move: {percent_change:+.4%} | {floor_status}")
            
            # ----------------------------------------------------
            # NOTIFICATION TYPE 2: LIQUIDITY HEATMAP KEY ZONE ENTRY
            # ----------------------------------------------------
            if heatmap_floor > 0.0:
                # Require price to be tightly converging near or past the lower floor block limit
                target_trigger_zone = heatmap_floor * (1 + HEATMAP_BUFFER_PERCENT)
                
                if current_price <= target_trigger_zone:
                    # Check 10-minute cooldown (600 seconds) to prevent spamming
                    if current_time - LAST_ZONE_ALERT_TIME[symbol] >= 600:
                        LAST_ZONE_ALERT_TIME[symbol] = current_time
                        zone_msg = f"🧱 LIQUIDITY ZONE ENTRY: {display_name} has converged tightly toward the institutional heatmap floor!\nPrice: {price_format}\nTarget Trigger Level: {target_trigger_zone:.5f} (Floor: {heatmap_floor:.5f})"
                        print(f"🚨 NOTIFICATION (TYPE 2): {zone_msg}")
                        send_alert(zone_msg)

            # ----------------------------------------------------
            # NOTIFICATION TYPE 1: TRADITIONAL VELOCITY FLASH CRASH
            # ----------------------------------------------------
            if len(history) >= 2:
                if percent_change <= -current_threshold:
                    crash_msg = f"📉 FLASH CRASH: {display_name} collapsed {percent_change:.2%} inside the trailing 5-minute window! (Price: {price_format})"
                    print(f"🚨 NOTIFICATION (TYPE 1): {crash_msg}")
                    send_alert(crash_msg)
                    history.clear()
                elif percent_change >= current_threshold:
                    history.clear()

def on_error(ws, error): print(f"❌ Error: {error}")
def on_close(ws, c_code, c_msg): trigger_next_runner()

def on_open(ws):
    print(f"📡 Initializing symbols stream updates...")
    for symbol in SYMBOLS:
        ws.send(json.dumps({"ticks": symbol}))
        time.sleep(0.2)

if __name__ == "__main__":
    print("🚀 Booting real-time Volatility & Heatmap Scanner...")
    calculate_heatmap_floors()
    
    price_histories = {symbol: deque(maxlen=MAX_LEN) for symbol in SYMBOLS}
    last_processed_times = {symbol: 0 for symbol in SYMBOLS}
    
    ws_url = "wss://ws.derivws.com/websockets/v3?app_id=1"
    ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close)
    ws.run_forever(ping_interval=10, ping_timeout=5)
    
