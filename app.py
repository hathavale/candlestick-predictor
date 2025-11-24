# app.py
import streamlit as st
import pandas as pd
import requests
from talib import abstract
import asyncio
from telegram import Bot
import hashlib
import os

# Helper function to get secrets from either st.secrets or environment variables
def get_secret(key, default=""):
    try:
        return st.secrets.get(key, default)
    except:
        return os.environ.get(key, default)

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None

# Login function
def login_page():
    st.title("🔐 Login to Candlestick Predictor")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### Please sign in to continue")
        
        username = st.text_input("Username", placeholder="Enter username")
        password = st.text_input("Password", type="password", placeholder="Enter password")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            if st.button("🔓 Login", use_container_width=True, type="primary"):
                if not username or not password:
                    st.error("❌ Please enter both username and password")
                else:
                    # Check credentials from secrets or environment variables
                    admin_user = get_secret("ADMIN_USER_ID", "")
                    admin_pass = get_secret("ADMIN_PASS", "")
                    guest_user = get_secret("GUEST_USER_ID", "")
                    guest_pass = get_secret("USER_PASS", "")
                    
                    if username == admin_user and password == admin_pass:
                        st.session_state.authenticated = True
                        st.session_state.username = "admin"
                        st.success("✅ Login successful! Welcome Admin!")
                        st.rerun()
                    elif username == guest_user and password == guest_pass:
                        st.session_state.authenticated = True
                        st.session_state.username = "guest"
                        st.success("✅ Login successful! Welcome Guest!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password")
        
        with col_b:
            if st.button("ℹ️ Help", use_container_width=True):
                st.info("Contact your administrator for login credentials.")
        
        st.markdown("---")
        st.caption("🔒 Secure access to Candlestick Prediction System")

# Logout function
def logout():
    st.session_state.authenticated = False
    st.session_state.username = None
    st.rerun()

# Check authentication
if not st.session_state.authenticated:
    login_page()
    st.stop()

# Main app (only visible after login)
st.title("Candlestick Predictor (Regular + After Hours)")

# Show logged in user and logout button in sidebar
with st.sidebar:
    st.markdown(f"### 👤 Logged in as: **{st.session_state.username}**")
    if st.button("🚪 Logout", use_container_width=True):
        logout()

# Sidebar for shared inputs
with st.sidebar:
    st.header("Settings")
    API_KEY = get_secret("ALPHA_VANTAGE_API_KEY", "demo")
    
    # API Status indicator
    if API_KEY and API_KEY != "demo":
        st.success("🚀 Premium API: Real-time data (600 calls/min)")
    else:
        st.warning("⚠️ Demo API: Limited data access")
    
    ticker = st.text_input("Ticker", "AAPL").upper()
    interval = st.selectbox("Interval", ["1min", "5min", "15min", "30min", "60min"], index=2)
    include_extended = st.checkbox("Include After-Hours", True)
    
    with st.expander("Advanced"):
        col1, col2 = st.columns(2)
        with col1:
            use_momentum = st.checkbox("RSI & Volume Momentum", True)
            use_trend = st.checkbox("Trend Analysis (SMA)", True)
            use_macd = st.checkbox("MACD Signals", True)
            use_obv = st.checkbox("On-Balance Volume", False)
            use_stoch_rsi = st.checkbox("Stochastic RSI", False)
        with col2:
            use_fibonacci = st.checkbox("Fibonacci Retracements", False)
            use_msb = st.checkbox("Market Structure Break", False)
            use_supply_demand = st.checkbox("Supply/Demand Zones", False)
        sensitivity = st.slider("Signal Threshold", 0, 10, 4)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["Live Signal", "Backtest", "Optimize", "Messages"])

# Shared data fetch function
def fetch_data(ticker, interval, extended, full=False):
    extended_param = "&extended_hours=true" if extended else ""
    size = "full" if full else "compact"
    # Use adjusted=false for real-time data without adjustments
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={ticker}&interval={interval}&outputsize={size}&apikey={API_KEY}{extended_param}&adjusted=false"
    resp = requests.get(url).json()
    
    # Check for rate limit or errors
    if "Note" in resp:
        st.warning(f"⚠️ API Note: {resp['Note']}")
        return None
    if "Error Message" in resp:
        st.error(f"API Error: {resp['Error Message']}")
        return None
    if "Information" in resp:
        st.error(f"API Info: {resp['Information']}")
        return None
        
    ts_key = f"Time Series ({interval})"
    if ts_key not in resp:
        st.error("No data. Check ticker.")
        return None
    df = pd.DataFrame.from_dict(resp[ts_key], orient="index")
    df = df.astype(float)
    df.index = pd.to_datetime(df.index)
    # Localize to US/Eastern timezone (Alpha Vantage uses ET)
    if df.index.tzinfo is None:
        df.index = df.index.tz_localize('US/Eastern')
    df.sort_index(inplace=True)
    df.columns = ["open", "high", "low", "close", "volume"]
    return df

# Calculate all advanced indicators
def calculate_indicators(df, use_momentum, use_trend, use_macd, use_obv, use_stoch_rsi, use_fibonacci, use_msb, use_supply_demand):
    # MACD
    if use_macd:
        df['MACD'], df['MACD_signal'], df['MACD_hist'] = abstract.MACD(df, fastperiod=12, slowperiod=26, signalperiod=9)
    
    # RSI and Volume
    if use_momentum:
        df['RSI'] = abstract.RSI(df, timeperiod=14)
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
    
    # Trend (SMA)
    if use_trend:
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        df['SMA_200'] = df['close'].rolling(window=200).mean()
    
    # On-Balance Volume
    if use_obv:
        df['OBV'] = (df['volume'] * ((df['close'] > df['close'].shift(1)).astype(int) - (df['close'] < df['close'].shift(1)).astype(int))).cumsum()
        df['OBV_SMA'] = df['OBV'].rolling(window=20).mean()
    
    # Stochastic RSI
    if use_stoch_rsi:
        rsi = abstract.RSI(df, timeperiod=14)
        stoch_rsi = (rsi - rsi.rolling(14).min()) / (rsi.rolling(14).max() - rsi.rolling(14).min()) * 100
        df['STOCH_RSI'] = stoch_rsi
    
    # Fibonacci Retracement Levels
    if use_fibonacci:
        lookback = min(50, len(df))
        recent = df.iloc[-lookback:]
        high = recent['high'].max()
        low = recent['low'].min()
        diff = high - low
        df['FIB_236'] = high - 0.236 * diff
        df['FIB_382'] = high - 0.382 * diff
        df['FIB_500'] = high - 0.500 * diff
        df['FIB_618'] = high - 0.618 * diff
    
    # Market Structure Break
    if use_msb:
        df['swing_high'] = df['high'].rolling(window=5, center=True).max()
        df['swing_low'] = df['low'].rolling(window=5, center=True).min()
        df['is_swing_high'] = df['high'] == df['swing_high']
        df['is_swing_low'] = df['low'] == df['swing_low']
    
    # Supply and Demand Zones
    if use_supply_demand:
        df['supply_zone'] = df['high'].rolling(window=20).quantile(0.95)
        df['demand_zone'] = df['low'].rolling(window=20).quantile(0.05)
    
    return df

# Advanced scoring function
def calculate_score(current, df, use_momentum, use_trend, use_macd, use_obv, use_stoch_rsi, use_fibonacci, use_msb, use_supply_demand, sensitivity):
    score = 0
    signals = []
    
    # 1. Candlestick patterns
    if current['CDLENGULFING'] == 100: score += 3; signals.append("Bullish Engulfing")
    if current['CDLENGULFING'] == -100: score -= 3; signals.append("Bearish Engulfing")
    if current['CDLMORNINGSTAR'] == 100: score += 4; signals.append("Morning Star")
    if current['CDLEVENINGSTAR'] == -100: score -= 4; signals.append("Evening Star")
    if current['CDLHAMMER'] == 100: score += 2; signals.append("Hammer")
    if current['CDLDOJI'] == 100: score += 1; signals.append("Doji")
    if current['CDL3WHITESOLDIERS'] == 100: score += 3; signals.append("Three White Soldiers")
    if current['CDL3BLACKCROWS'] == -100: score -= 3; signals.append("Three Black Crows")
    if current['CDLHARAMI'] == 100: score += 2; signals.append("Bullish Harami")
    if current['CDLPIERCING'] == 100: score += 2; signals.append("Piercing Pattern")
    if current['CDLDARKCLOUDCOVER'] == -100: score -= 2; signals.append("Dark Cloud Cover")
    
    # 2. MACD Signals (Strongest momentum filter)
    if use_macd and 'MACD' in current:
        try:
            if not pd.isna(current['MACD']):
                macd = float(current['MACD'])
                signal = float(current['MACD_signal'])
                hist = float(current['MACD_hist'])
                prev_hist = float(df['MACD_hist'].iloc[-2]) if len(df) > 1 and not pd.isna(df['MACD_hist'].iloc[-2]) else 0.0
                
                # Bullish MACD
                if macd > signal and hist > 0:
                    score += 4
                    signals.append("MACD Bullish")
                if macd > signal and hist > prev_hist and hist > 0:
                    score += 5
                    signals.append("MACD Momentum Surge")
                if macd > 0 and macd > signal:
                    score += 6
                    signals.append("MACD Above Zero (Strong Bull)")
                
                # Bearish MACD
                if macd < signal and hist < 0:
                    score -= 4
                    signals.append("MACD Bearish")
                if hist < prev_hist and hist < 0:
                    score -= 5
                    signals.append("MACD Momentum Fade")
                if macd < 0 and macd < signal:
                    score -= 6
                    signals.append("MACD Below Zero (Strong Bear)")
        except (ValueError, TypeError, KeyError):
            pass
    
    # 3. RSI Divergence + Volume Spike
    if use_momentum and 'RSI' in current and not pd.isna(current['RSI']):
        rsi_val = float(current['RSI'])
        recent = df.iloc[-10:] if len(df) >= 10 else df
        
        # RSI Divergence
        if len(recent) >= 3:
            if recent['close'].is_monotonic_decreasing and recent['RSI'].is_monotonic_increasing and rsi_val < 45:
                score += 7
                signals.append("Bullish RSI Divergence")
            if recent['close'].is_monotonic_increasing and recent['RSI'].is_monotonic_decreasing and rsi_val > 55:
                score -= 7
                signals.append("Bearish RSI Divergence")
        
        # Standard RSI levels
        if rsi_val < 30:
            score += 2
            signals.append("RSI Oversold")
        elif rsi_val > 70:
            score -= 2
            signals.append("RSI Overbought")
        
        # Volume confirmation
        if 'volume_ratio' in current and float(current['volume_ratio']) > 2.0:
            score += 3 if score > 0 else -3
            signals.append("Volume Explosion")
        elif 'volume_ratio' in current and float(current['volume_ratio']) > 1.5:
            if score > 0:
                score += 1
                signals.append("High Volume (Bullish)")
            elif score < 0:
                score -= 1
                signals.append("High Volume (Bearish)")
    
    # 4. Trend Filter – Kill counter-trend noise (Golden Cross)
    if use_trend and 'SMA_20' in current and 'SMA_50' in current:
        if not pd.isna(current['SMA_20']) and not pd.isna(current['SMA_50']):
            # Price position relative to SMAs
            if float(current['close']) > float(current['SMA_20']) and float(current['close']) > float(current['SMA_50']):
                score += 2
                signals.append("Uptrend (Above SMAs)")
            elif float(current['close']) < float(current['SMA_20']) and float(current['close']) < float(current['SMA_50']):
                score -= 2
                signals.append("Downtrend (Below SMAs)")
            
            # Golden/Death Cross
            if float(current['SMA_20']) > float(current['SMA_50']):
                prev_20 = float(df['SMA_20'].iloc[-2]) if len(df) > 1 else float(current['SMA_20'])
                prev_50 = float(df['SMA_50'].iloc[-2]) if len(df) > 1 else float(current['SMA_50'])
                if prev_20 <= prev_50:  # Just crossed
                    score += 5
                    signals.append("Golden Cross (Fresh)")
                else:
                    score += 1
                    signals.append("Golden Cross")
            elif float(current['SMA_20']) < float(current['SMA_50']):
                prev_20 = float(df['SMA_20'].iloc[-2]) if len(df) > 1 else float(current['SMA_20'])
                prev_50 = float(df['SMA_50'].iloc[-2]) if len(df) > 1 else float(current['SMA_50'])
                if prev_20 >= prev_50:  # Just crossed
                    score -= 5
                    signals.append("Death Cross (Fresh)")
                else:
                    score -= 1
                    signals.append("Death Cross")
            
            # Strong trend filter using SMA_200
            if 'SMA_200' in current and not pd.isna(current['SMA_200']):
                if float(current['close']) > float(current['SMA_200']):
                    score = max(score, 0)  # Only bullish signals
                else:
                    score = min(score, 0)  # Only bearish signals
    
    # 5. On-Balance Volume
    if use_obv and 'OBV' in current and 'OBV_SMA' in current:
        if not pd.isna(current['OBV']) and not pd.isna(current['OBV_SMA']):
            if float(current['OBV']) > float(current['OBV_SMA']):
                score += 2
                signals.append("OBV Bullish (Accumulation)")
            else:
                score -= 2
                signals.append("OBV Bearish (Distribution)")
    
    # 6. Stochastic RSI
    if use_stoch_rsi and 'STOCH_RSI' in current and not pd.isna(current['STOCH_RSI']):
        if float(current['STOCH_RSI']) < 20:
            score += 3
            signals.append("Stoch RSI Oversold")
        elif float(current['STOCH_RSI']) > 80:
            score -= 3
            signals.append("Stoch RSI Overbought")
    
    # 7. Fibonacci Retracements
    if use_fibonacci and 'FIB_618' in current:
        price = float(current['close'])
        if not pd.isna(current['FIB_618']):
            # Price at key Fibonacci levels
            if abs(price - float(current['FIB_618'])) / price < 0.005:  # Within 0.5%
                score += 4
                signals.append("At Fib 61.8% (Golden Ratio)")
            elif abs(price - float(current['FIB_500'])) / price < 0.005:
                score += 2
                signals.append("At Fib 50%")
            elif abs(price - float(current['FIB_382'])) / price < 0.005:
                score += 2
                signals.append("At Fib 38.2%")
    
    # 8. Market Structure Break
    if use_msb and 'is_swing_high' in current and 'is_swing_low' in current:
        recent_highs = df[df['is_swing_high'] == True].tail(2)
        recent_lows = df[df['is_swing_low'] == True].tail(2)
        
        # Break of structure (BOS)
        if len(recent_highs) >= 2 and float(current['close']) > float(recent_highs.iloc[-1]['high']):
            score += 5
            signals.append("Market Structure Break (Bullish)")
        if len(recent_lows) >= 2 and float(current['close']) < float(recent_lows.iloc[-1]['low']):
            score -= 5
            signals.append("Market Structure Break (Bearish)")
    
    # 9. Supply and Demand Zones
    if use_supply_demand and 'supply_zone' in current and 'demand_zone' in current:
        if not pd.isna(current['supply_zone']) and not pd.isna(current['demand_zone']):
            # Price at supply zone (resistance)
            if float(current['close']) >= float(current['supply_zone']):
                score -= 3
                signals.append("At Supply Zone (Resistance)")
            # Price at demand zone (support)
            elif float(current['close']) <= float(current['demand_zone']):
                score += 3
                signals.append("At Demand Zone (Support)")
    
    return score, signals

with tab1:
    st.header("Live Signal")
    
    # Check current market status upfront
    now_et = pd.Timestamp.now(tz='US/Eastern')
    is_weekend_now = now_et.weekday() >= 5
    is_trading_hours = 9 <= now_et.hour < 16
    
    if is_weekend_now:
        st.warning("📅 **WEEKEND**: Market is closed. Data shown will be from last Friday's trading session.")
    elif not is_trading_hours:
        if now_et.hour < 9:
            st.info("🌅 **PRE-MARKET**: Regular trading starts at 9:30 AM ET. Showing previous close data.")
        else:
            st.info("🌆 **AFTER-HOURS**: Regular trading ended at 4:00 PM ET. Showing last trading session data.")
    else:
        st.success(f"🟢 **MARKET OPEN**: Live trading data available | Current time: {now_et.strftime('%I:%M %p ET')}")
    
    # Real-time monitoring controls
    col_btn1, col_btn2, col_refresh = st.columns([2, 2, 2])
    with col_btn1:
        manual_refresh = st.button("🔄 Get Live Prediction", key="live", use_container_width=True, type="primary")
    with col_btn2:
        auto_refresh = st.checkbox("Auto-Refresh", value=False, help="Automatically refresh data every 30 seconds (for 1min/5min intervals)")
    with col_refresh:
        if auto_refresh:
            refresh_interval = st.selectbox("Refresh Rate", [30, 60, 120], format_func=lambda x: f"{x}s", index=0)
        else:
            refresh_interval = None
    
    # Auto-refresh logic
    if auto_refresh and refresh_interval:
        import time
        time.sleep(refresh_interval)
        st.rerun()
    
    if manual_refresh or auto_refresh:
        with st.spinner("Fetching real-time data..."):
            df = fetch_data(ticker, interval, include_extended)
            if df is None: st.stop()
            
            # Calculate all candlestick patterns
            for p in ['CDLDOJI', 'CDLHAMMER', 'CDLENGULFING', 'CDLMORNINGSTAR', 'CDLEVENINGSTAR',
                      'CDL3WHITESOLDIERS', 'CDL3BLACKCROWS', 'CDLHARAMI', 'CDLPIERCING', 'CDLDARKCLOUDCOVER']:
                df[p] = getattr(abstract, p)(df)
            
            # Calculate all indicators
            df = calculate_indicators(df, use_momentum, use_trend, use_macd, use_obv, use_stoch_rsi, use_fibonacci, use_msb, use_supply_demand)
            
            latest = df.iloc[-1]
            latest_time = df.index[-1]
            current_time = pd.Timestamp.now(tz='US/Eastern')
            
            # Calculate data freshness (both are now timezone-aware)
            time_diff = current_time - latest_time
            minutes_old = int(time_diff.total_seconds() / 60)
            
            # Determine market status
            current_hour = current_time.hour
            current_minute = current_time.minute
            current_weekday = current_time.weekday()
            latest_hour = latest_time.hour
            
            is_weekend = current_weekday >= 5
            # Market is open 9:30 AM - 4:00 PM ET (9.5 to 16.0 in decimal hours)
            current_time_decimal = current_hour + (current_minute / 60.0)
            is_market_open = (9.5 <= current_time_decimal < 16.0) and not is_weekend
            is_after_hours = latest_hour < 9 or latest_hour >= 16
            market_session = "After Hours" if is_after_hours else "Regular Hours"
            
            # Data freshness indicator - only meaningful during market hours
            interval_minutes = {"1min": 1, "5min": 5, "15min": 15, "30min": 30, "60min": 60}
            expected_delay = interval_minutes.get(interval, 15)
            # During market hours: data is fresh if within expected interval + 5 min buffer
            # Outside market hours: always consider "expected" since no new data is generated
            is_fresh = minutes_old <= (expected_delay + 5) if is_market_open else True
            
            # Create sub-tabs for Live Signal and Debug Info
            signal_tab, debug_tab = st.tabs(["📊 Prediction", "🔍 Debug Info"])
            
            with signal_tab:
                # Market status banner - show appropriate message based on market hours
                if is_weekend:
                    st.info(f"📅 **WEEKEND** - Market Closed | Showing Last Trading Session: {latest_time.strftime('%a %m/%d %I:%M %p')}")
                elif not is_market_open:
                    if current_hour < 9 or (current_hour == 9 and current_minute < 30):
                        st.info(f"🌅 **PRE-MARKET** - Opens at 9:30 AM ET | Last Close: {latest_time.strftime('%a %m/%d %I:%M %p')}")
                    else:
                        st.info(f"🌆 **AFTER-HOURS** - Closed at 4:00 PM ET | Last Session: {latest_time.strftime('%a %m/%d %I:%M %p')}")
                else:
                    # Market is OPEN - show live data status
                    if is_fresh:
                        st.success(f"🟢 **LIVE DATA** - Market Open | Updated {minutes_old} min ago | {latest_time.strftime('%I:%M %p')}")
                    else:
                        st.warning(f"⚠️ **DELAYED DATA** - Data is {minutes_old} min old (Expected: <{expected_delay + 5} min) | {latest_time.strftime('%I:%M %p')}")
                
                score, signals = calculate_score(latest, df, use_momentum, use_trend, use_macd, use_obv, use_stoch_rsi, use_fibonacci, use_msb, use_supply_demand, sensitivity)
                score = float(score)  # Ensure score is numeric
                
                direction = "BULLISH" if score > sensitivity else "BEARISH" if score < -sensitivity else "NEUTRAL"
                color = "green" if direction=="BULLISH" else "red" if direction=="BEARISH" else "gray"
                
                # After-hours volatility warning
                volatility_note = ""
                if is_after_hours:
                    volatility_note = " ⚠️ *Note: After-hours trading typically has lower volume and higher volatility*"
                
                st.markdown(f"### Next {interval} ({market_session}) → **:{color}[{direction}]**{volatility_note}")
                st.write("**Patterns:**", ", ".join(signals) or "None")
                st.write(f"**Signal Strength:** {score}")
                
                # Timestamp info
                st.caption(f"📡 Data fetched from Alpha Vantage at: {current_time.strftime('%I:%M:%S %p %Z')}")
                st.caption(f"📊 Latest candle timestamp: {latest_time.strftime('%a %m/%d %I:%M %p %Z')}")
            
            with debug_tab:
                st.write("**API & Data Info:**")
                st.write(f"🔌 API Endpoint: TIME_SERIES_INTRADAY (adjusted=false, real-time)")
                st.write(f"⏱️ Fetch Time: {current_time.strftime('%Y-%m-%d %I:%M:%S %p %Z')}")
                st.write(f"📊 Total Candles Retrieved: {len(df)}")
                st.write(f"📅 Data Range: {df.index[0].strftime('%m/%d %I:%M %p')} to {df.index[-1].strftime('%m/%d %I:%M %p')}")
                st.write(f"⏲️ Latest Candle: {latest_time.strftime('%Y-%m-%d %H:%M')} ({market_session})")
                st.write(f"⌚ Data Age: {minutes_old} minutes (Expected: ≤{expected_delay + 5} min during market hours)")
                st.write(f"🏦 Market Status: {'OPEN' if is_market_open else 'CLOSED'} | Weekend: {is_weekend}")
                st.write("")
                st.write("**Latest OHLC:**")
                st.write(f"Open: {float(latest['open']):.2f}, High: {float(latest['high']):.2f}, Low: {float(latest['low']):.2f}, Close: {float(latest['close']):.2f}")
                st.write(f"Pattern Values - CDLENGULFING: {latest['CDLENGULFING']}, CDLMORNINGSTAR: {latest['CDLMORNINGSTAR']}, CDLEVENINGSTAR: {latest['CDLEVENINGSTAR']}")
                st.write(f"CDLHAMMER: {latest['CDLHAMMER']}, CDLDOJI: {latest['CDLDOJI']}, CDL3WHITESOLDIERS: {latest['CDL3WHITESOLDIERS']}, CDL3BLACKCROWS: {latest['CDL3BLACKCROWS']}")
                st.write(f"CDLHARAMI: {latest['CDLHARAMI']}, CDLPIERCING: {latest['CDLPIERCING']}, CDLDARKCLOUDCOVER: {latest['CDLDARKCLOUDCOVER']}")
                if use_macd and 'MACD' in latest:
                    try:
                        st.write(f"MACD: {float(latest['MACD']):.4f}, Signal: {float(latest['MACD_signal']):.4f}, Hist: {float(latest['MACD_hist']):.4f}" if not pd.isna(latest['MACD']) else "MACD: N/A")
                    except (ValueError, TypeError):
                        st.write("MACD: N/A")
                if use_momentum:
                    try:
                        st.write(f"RSI: {float(latest['RSI']):.2f}" if not pd.isna(latest['RSI']) else "RSI: N/A")
                        st.write(f"Volume Ratio: {float(latest['volume_ratio']):.2f}" if not pd.isna(latest['volume_ratio']) else "Volume Ratio: N/A")
                    except (ValueError, TypeError):
                        st.write("RSI/Volume: N/A")
                if use_trend:
                    try:
                        st.write(f"SMA_20: {float(latest['SMA_20']):.2f}, SMA_50: {float(latest['SMA_50']):.2f}" if not pd.isna(latest['SMA_20']) else "SMAs: N/A")
                    except (ValueError, TypeError):
                        st.write("SMAs: N/A")
                if use_obv and 'OBV' in latest:
                    try:
                        st.write(f"OBV: {float(latest['OBV']):.0f}" if not pd.isna(latest['OBV']) else "OBV: N/A")
                    except (ValueError, TypeError):
                        st.write("OBV: N/A")
                if use_stoch_rsi and 'STOCH_RSI' in latest:
                    try:
                        st.write(f"Stochastic RSI: {float(latest['STOCH_RSI']):.2f}" if not pd.isna(latest['STOCH_RSI']) else "Stoch RSI: N/A")
                    except (ValueError, TypeError):
                        st.write("Stoch RSI: N/A")
                if use_fibonacci and 'FIB_618' in latest:
                    try:
                        st.write(f"Fib Levels - 61.8%: {float(latest['FIB_618']):.2f}, 50%: {float(latest['FIB_500']):.2f}, 38.2%: {float(latest['FIB_382']):.2f}" if not pd.isna(latest['FIB_618']) else "Fib: N/A")
                    except (ValueError, TypeError):
                        st.write("Fib: N/A")

with tab2:
    st.header("Backtest")
    if st.button("Run Backtest", key="back"):
        with st.spinner("Running backtest..."):
            df = fetch_data(ticker, interval, include_extended, full=True)
            if df is None: st.stop()
            
            # Calculate patterns for all candles
            for p in ['CDLDOJI', 'CDLHAMMER', 'CDLENGULFING', 'CDLMORNINGSTAR', 'CDLEVENINGSTAR',
                      'CDL3WHITESOLDIERS', 'CDL3BLACKCROWS', 'CDLHARAMI', 'CDLPIERCING', 'CDLDARKCLOUDCOVER']:
                df[p] = getattr(abstract, p)(df)
            
            # Add momentum indicators for backtest
            if use_momentum:
                df['RSI'] = abstract.RSI(df, timeperiod=14)
                df['volume_sma'] = df['volume'].rolling(window=20).mean()
                df['volume_ratio'] = df['volume'] / df['volume_sma']
            
            # Add trend indicators for backtest
            if use_trend:
                df['SMA_20'] = df['close'].rolling(window=20).mean()
                df['SMA_50'] = df['close'].rolling(window=50).mean()
            
            # Backtest logic: For each candle, predict next candle direction
            correct_predictions = 0
            total_predictions = 0
            bullish_correct = 0
            bullish_total = 0
            bearish_correct = 0
            bearish_total = 0
            
            # Start from index 50 to have enough data for indicators
            start_idx = 50 if use_trend else 20 if use_momentum else 0
            
            for i in range(start_idx, len(df) - 1):
                current = df.iloc[i]
                next_candle = df.iloc[i + 1]
                
                # Calculate score for current candle
                score = 0
                
                # Candlestick patterns
                if current['CDLENGULFING'] == 100: score += 3
                if current['CDLENGULFING'] == -100: score -= 3
                if current['CDLMORNINGSTAR'] == 100: score += 4
                if current['CDLEVENINGSTAR'] == -100: score -= 4
                if current['CDLHAMMER'] == 100: score += 2
                if current['CDLDOJI'] == 100: score += 1
                if current['CDL3WHITESOLDIERS'] == 100: score += 3
                if current['CDL3BLACKCROWS'] == -100: score -= 3
                if current['CDLHARAMI'] == 100: score += 2
                if current['CDLPIERCING'] == 100: score += 2
                if current['CDLDARKCLOUDCOVER'] == -100: score -= 2
                
                # Add RSI momentum
                if use_momentum and not pd.isna(current['RSI']):
                    if current['RSI'] < 30: score += 2
                    elif current['RSI'] > 70: score -= 2
                    
                    if not pd.isna(current['volume_ratio']) and current['volume_ratio'] > 1.5:
                        if score > 0: score += 1
                        elif score < 0: score -= 1
                
                # Add trend analysis
                if use_trend and not pd.isna(current['SMA_20']) and not pd.isna(current['SMA_50']):
                    if current['close'] > current['SMA_20'] and current['close'] > current['SMA_50']:
                        score += 2
                    elif current['close'] < current['SMA_20'] and current['close'] < current['SMA_50']:
                        score -= 2
                    
                    if current['SMA_20'] > current['SMA_50']:
                        score += 1
                    elif current['SMA_20'] < current['SMA_50']:
                        score -= 1
                
                # Determine prediction with user's threshold
                prediction = "BULLISH" if score > sensitivity else "BEARISH" if score < -sensitivity else "NEUTRAL"
                
                # Skip neutral predictions in accuracy calculation
                if prediction == "NEUTRAL":
                    continue
                
                # Actual direction of next candle
                actual_direction = "BULLISH" if next_candle['close'] > current['close'] else "BEARISH"
                
                total_predictions += 1
                if prediction == actual_direction:
                    correct_predictions += 1
                
                # Track bullish/bearish accuracy separately
                if prediction == "BULLISH":
                    bullish_total += 1
                    if actual_direction == "BULLISH":
                        bullish_correct += 1
                elif prediction == "BEARISH":
                    bearish_total += 1
                    if actual_direction == "BEARISH":
                        bearish_correct += 1
            
            # Display results
            accuracy = (correct_predictions / total_predictions * 100) if total_predictions > 0 else 0
            bullish_accuracy = (bullish_correct / bullish_total * 100) if bullish_total > 0 else 0
            bearish_accuracy = (bearish_correct / bearish_total * 100) if bearish_total > 0 else 0
            
            st.markdown("### Backtest Results")
            st.write(f"**Total Candles Analyzed:** {len(df)}")
            st.write(f"**Predictions Made (excl. Neutral):** {total_predictions}")
            st.write(f"**Overall Accuracy:** {accuracy:.2f}% ({correct_predictions}/{total_predictions})")
            st.write(f"**Bullish Predictions:** {bullish_total} | Accuracy: {bullish_accuracy:.2f}% ({bullish_correct}/{bullish_total})")
            st.write(f"**Bearish Predictions:** {bearish_total} | Accuracy: {bearish_accuracy:.2f}% ({bearish_correct}/{bearish_total})")
            
            # Performance gauge
            if accuracy >= 60:
                performance = "🟢 Strong"
            elif accuracy >= 50:
                performance = "🟡 Moderate"
            else:
                performance = "🔴 Weak"
            
            st.markdown(f"**Performance Rating:** {performance}")
            st.info("Note: Random guessing would yield ~50% accuracy. Values above 55% suggest the indicator has predictive value.")

with tab3:
    st.header("Optimize Indicators")
    st.write("Discover optimal indicator combinations using fractional factorial design with interaction analysis.")
    st.info("🔬 This experimental design tests 2-way and 3-way interactions between indicators to find synergistic combinations.")
    
    if st.button("Find Optimal Configuration", key="optimize"):
        with st.spinner("Running optimization experiment (testing 64 configurations)..."):
            df = fetch_data(ticker, interval, include_extended, full=True)
            if df is None: st.stop()
            
            # Calculate ALL indicators upfront (candlesticks always included)
            df = calculate_indicators(df, True, True, True, True, True, True, True, True)
            for p in ['CDLDOJI', 'CDLHAMMER', 'CDLENGULFING', 'CDLMORNINGSTAR', 'CDLEVENINGSTAR',
                      'CDL3WHITESOLDIERS', 'CDL3BLACKCROWS', 'CDLHARAMI', 'CDLPIERCING', 'CDLDARKCLOUDCOVER']:
                df[p] = getattr(abstract, p)(df)
            
            # Fractional factorial design (2^6 = 64 experiments) for 6 key indicator groups
            # Testing: MACD, RSI_Divergence, Volume, Trend, OBV, StochRSI
            # (Fibonacci, MSB, Supply/Demand excluded to keep experiment size manageable)
            import itertools
            experiments = list(itertools.product([False, True], repeat=6))
            
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, (use_macd, use_rsi_div, use_volume, use_trend, use_obv, use_stoch) in enumerate(experiments):
                status_text.text(f"Testing configuration {idx+1}/{len(experiments)}...")
                progress_bar.progress((idx + 1) / len(experiments))
                
                correct = total = 0
                bullish_correct = bullish_total = 0
                bearish_correct = bearish_total = 0
                
                # Start after enough data for all indicators
                start_idx = 200
                
                for i in range(start_idx, len(df) - 1):
                    current = df.iloc[i]
                    next_candle = df.iloc[i + 1]
                    
                    # Use the same scoring logic as calculate_score but with flags
                    score = 0
                    
                    # ALWAYS include candlestick patterns as baseline
                    if current['CDLENGULFING'] == 100: score += 3
                    if current['CDLENGULFING'] == -100: score -= 3
                    if current['CDLMORNINGSTAR'] == 100: score += 4
                    if current['CDLEVENINGSTAR'] == -100: score -= 4
                    if current['CDLHAMMER'] == 100: score += 2
                    if current['CDLDOJI'] == 100: score += 1
                    if current['CDL3WHITESOLDIERS'] == 100: score += 3
                    if current['CDL3BLACKCROWS'] == -100: score -= 3
                    if current['CDLHARAMI'] == 100: score += 2
                    if current['CDLPIERCING'] == 100: score += 2
                    if current['CDLDARKCLOUDCOVER'] == -100: score -= 2
                    
                    # MACD signals
                    if use_macd and not pd.isna(current['MACD']):
                        try:
                            macd_val = float(current['MACD'])
                            macd_sig = float(current['MACD_signal'])
                            macd_hist = float(current['MACD_hist'])
                            
                            if macd_val > macd_sig and macd_hist > 0:
                                score += 4 if abs(macd_hist) > 0.5 else 2
                            elif macd_val < macd_sig and macd_hist < 0:
                                score -= 4 if abs(macd_hist) > 0.5 else 2
                        except: pass
                    
                    # RSI with divergence
                    if use_rsi_div and not pd.isna(current['RSI']):
                        try:
                            rsi = float(current['RSI'])
                            if i >= start_idx + 5:
                                prev_rsi = float(df.iloc[i-5]['RSI'])
                                prev_close = float(df.iloc[i-5]['close'])
                                curr_close = float(current['close'])
                                
                                # Bullish divergence: price lower, RSI higher
                                if curr_close < prev_close and rsi > prev_rsi:
                                    score += 7
                                # Bearish divergence: price higher, RSI lower
                                elif curr_close > prev_close and rsi < prev_rsi:
                                    score -= 7
                            
                            if rsi < 30: score += 2
                            elif rsi > 70: score -= 2
                        except: pass
                    
                    # Volume spike
                    if use_volume and not pd.isna(current['volume_ratio']):
                        try:
                            vol_ratio = float(current['volume_ratio'])
                            if vol_ratio > 2.0:
                                if score > 0: score += 3
                                elif score < 0: score -= 3
                        except: pass
                    
                    # Trend with Golden/Death cross
                    if use_trend and not pd.isna(current['SMA_50']):
                        try:
                            sma20 = float(current['SMA_20'])
                            sma50 = float(current['SMA_50'])
                            sma200 = float(current['SMA_200'])
                            close = float(current['close'])
                            
                            # Golden cross detection
                            if i >= start_idx + 1:
                                prev_20 = float(df.iloc[i-1]['SMA_20'])
                                prev_50 = float(df.iloc[i-1]['SMA_50'])
                                
                                if sma20 > sma50 and prev_20 <= prev_50:
                                    score += 5
                                elif sma20 < sma50 and prev_20 >= prev_50:
                                    score -= 5
                            
                            # Trend alignment
                            if close > sma200:
                                score += 1
                            elif close < sma200:
                                score -= 1
                        except: pass
                    
                    # OBV
                    if use_obv and not pd.isna(current['OBV']):
                        try:
                            obv = float(current['OBV'])
                            obv_sma = float(current['OBV_SMA'])
                            if obv > obv_sma:
                                score += 2
                            elif obv < obv_sma:
                                score -= 2
                        except: pass
                    
                    # Stochastic RSI
                    if use_stoch and not pd.isna(current['STOCH_RSI']):
                        try:
                            stoch = float(current['STOCH_RSI'])
                            if stoch < 20:
                                score += 3
                            elif stoch > 80:
                                score -= 3
                        except: pass
                    
                    prediction = "BULLISH" if score > sensitivity else "BEARISH" if score < -sensitivity else "NEUTRAL"
                    if prediction == "NEUTRAL": continue
                    
                    actual = "BULLISH" if next_candle['close'] > current['close'] else "BEARISH"
                    total += 1
                    if prediction == actual: correct += 1
                    
                    if prediction == "BULLISH":
                        bullish_total += 1
                        if actual == "BULLISH": bullish_correct += 1
                    else:
                        bearish_total += 1
                        if actual == "BEARISH": bearish_correct += 1
                
                acc = (correct / total * 100) if total > 0 else 0
                bull_acc = (bullish_correct / bullish_total * 100) if bullish_total > 0 else 0
                bear_acc = (bearish_correct / bearish_total * 100) if bearish_total > 0 else 0
                
                results.append({
                    'MACD': use_macd,
                    'RSI_Div': use_rsi_div,
                    'Volume': use_volume,
                    'Trend': use_trend,
                    'OBV': use_obv,
                    'StochRSI': use_stoch,
                    'Accuracy': acc,
                    'Bullish_Acc': bull_acc,
                    'Bearish_Acc': bear_acc,
                    'Signals': total,
                    'Indicator_Count': sum([use_macd, use_rsi_div, use_volume, use_trend, use_obv, use_stoch])
                })
            
            progress_bar.empty()
            status_text.empty()
            
            # Analyze results
            results_df = pd.DataFrame(results)
            
            # Find best overall configuration
            best_idx = results_df['Accuracy'].idxmax()
            best_config = results_df.iloc[best_idx]
            
            # Analyze 2-way interactions
            st.markdown("### 🎯 Optimal Configuration Found")
            st.markdown(f"**Best Accuracy: {best_config['Accuracy']:.2f}%** ({int(best_config['Signals'])} signals)")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("#### ✅ Optimal Indicators:")
                for ind in ['MACD', 'RSI_Div', 'Volume', 'Trend', 'OBV', 'StochRSI']:
                    st.write(f"{'✓' if best_config[ind] else '✗'} {ind.replace('_', ' ')}")
            
            with col2:
                st.markdown("#### 📊 Performance:")
                st.metric("Overall", f"{best_config['Accuracy']:.1f}%")
                st.metric("Bullish", f"{best_config['Bullish_Acc']:.1f}%")
                st.metric("Bearish", f"{best_config['Bearish_Acc']:.1f}%")
            
            with col3:
                st.markdown("#### 🎲 Complexity:")
                st.metric("Active Indicators", int(best_config['Indicator_Count']))
                if best_config['Accuracy'] >= 60:
                    st.success("🟢 Strong")
                elif best_config['Accuracy'] >= 50:
                    st.warning("🟡 Moderate")
                else:
                    st.error("🔴 Weak")
            
            # Interaction Analysis
            st.markdown("### 🔬 Interaction Effects Analysis")
            
            # 2-way interactions
            st.markdown("#### 📈 Best 2-Way Indicator Combinations")
            indicators = ['MACD', 'RSI_Div', 'Volume', 'Trend', 'OBV', 'StochRSI']
            two_way = []
            
            for i, ind1 in enumerate(indicators):
                for ind2 in indicators[i+1:]:
                    # Find configs with both indicators ON
                    both_on = results_df[(results_df[ind1] == True) & (results_df[ind2] == True)]
                    # Find configs with both OFF
                    both_off = results_df[(results_df[ind1] == False) & (results_df[ind2] == False)]
                    
                    if len(both_on) > 0 and len(both_off) > 0:
                        interaction_effect = both_on['Accuracy'].mean() - both_off['Accuracy'].mean()
                        two_way.append({
                            'Indicator 1': ind1.replace('_', ' '),
                            'Indicator 2': ind2.replace('_', ' '),
                            'Interaction Effect': interaction_effect,
                            'Avg Accuracy (Both On)': both_on['Accuracy'].mean()
                        })
            
            two_way_df = pd.DataFrame(two_way).sort_values('Interaction Effect', ascending=False)
            st.dataframe(two_way_df.head(10).style.format({
                'Interaction Effect': '{:.2f}%',
                'Avg Accuracy (Both On)': '{:.2f}%'
            }), use_container_width=True)
            
            # 3-way interactions
            st.markdown("#### 🎲 Best 3-Way Indicator Combinations")
            three_way = []
            
            for i, ind1 in enumerate(indicators):
                for j, ind2 in enumerate(indicators[i+1:], i+1):
                    for ind3 in indicators[j+1:]:
                        # Find configs with all three ON
                        all_on = results_df[(results_df[ind1] == True) & (results_df[ind2] == True) & (results_df[ind3] == True)]
                        # Find configs with all three OFF
                        all_off = results_df[(results_df[ind1] == False) & (results_df[ind2] == False) & (results_df[ind3] == False)]
                        
                        if len(all_on) > 0 and len(all_off) > 0:
                            interaction_effect = all_on['Accuracy'].mean() - all_off['Accuracy'].mean()
                            three_way.append({
                                'Indicator 1': ind1.replace('_', ' '),
                                'Indicator 2': ind2.replace('_', ' '),
                                'Indicator 3': ind3.replace('_', ' '),
                                'Interaction Effect': interaction_effect,
                                'Avg Accuracy (All On)': all_on['Accuracy'].mean()
                            })
            
            three_way_df = pd.DataFrame(three_way).sort_values('Interaction Effect', ascending=False)
            st.dataframe(three_way_df.head(10).style.format({
                'Interaction Effect': '{:.2f}%',
                'Avg Accuracy (All On)': '{:.2f}%'
            }), use_container_width=True)
            
            # Top configurations
            st.markdown("### 📊 Top 10 Configurations")
            top_10 = results_df.nlargest(10, 'Accuracy')[['MACD', 'RSI_Div', 'Volume', 'Trend', 'OBV', 'StochRSI', 'Accuracy', 'Signals']].copy()
            top_10['Accuracy'] = top_10['Accuracy'].apply(lambda x: f"{x:.2f}%")
            st.dataframe(top_10, use_container_width=True)

with tab4:
    st.header("📨 Telegram Messages")
    st.write("Send trading signals and alerts via Telegram bot.")
    
    # Get API key from secrets or environment
    TELEGRAM_API_KEY = get_secret("TELEGRAM_API_KEY", "")
    
    if not TELEGRAM_API_KEY:
        st.error("❌ Telegram API key not found in secrets.toml")
    else:
        # Input fields
        col1, col2 = st.columns([2, 1])
        
        with col1:
            chat_id = st.text_input("Chat ID", placeholder="123456789", help="Your Telegram chat ID")
        
        with col2:
            st.write("")
            st.write("")
            test_mode = st.checkbox("Test Mode", value=True)
        
        message = st.text_area(
            "Message",
            placeholder="Enter your message here...",
            height=150,
            help="Type the message you want to send to Telegram"
        )
        
        # Quick message templates
        st.markdown("#### 📋 Quick Templates")
        template_cols = st.columns(4)
        
        with template_cols[0]:
            if st.button("🟢 Bullish Signal"):
                message = f"🟢 BULLISH SIGNAL\n\nTicker: {ticker}\nInterval: {interval}\nTime: {pd.Timestamp.now(tz='US/Eastern').strftime('%Y-%m-%d %H:%M %Z')}"
                st.rerun()
        
        with template_cols[1]:
            if st.button("🔴 Bearish Signal"):
                message = f"🔴 BEARISH SIGNAL\n\nTicker: {ticker}\nInterval: {interval}\nTime: {pd.Timestamp.now(tz='US/Eastern').strftime('%Y-%m-%d %H:%M %Z')}"
                st.rerun()
        
        with template_cols[2]:
            if st.button("⚠️ Alert"):
                message = f"⚠️ ALERT\n\nTicker: {ticker}\nInterval: {interval}\nTime: {pd.Timestamp.now(tz='US/Eastern').strftime('%Y-%m-%d %H:%M %Z')}"
                st.rerun()
        
        with template_cols[3]:
            if st.button("ℹ️ Test Message"):
                message = "Test message from Candlestick Predictor Bot! 🤖"
                st.rerun()
        
        # Send button
        st.markdown("---")
        
        if st.button("📤 Send Message", type="primary", use_container_width=True):
            if not chat_id:
                st.error("❌ Please enter a Chat ID")
            elif not message:
                st.error("❌ Please enter a message")
            else:
                try:
                    with st.spinner("Sending message..."):
                        # Create async function to send message
                        async def send_telegram_message():
                            bot = Bot(token=TELEGRAM_API_KEY)
                            async with bot:
                                await bot.send_message(chat_id=int(chat_id), text=message)
                        
                        # Run async function
                        asyncio.run(send_telegram_message())
                    
                    st.success(f"✅ Message sent successfully to chat ID: {chat_id}")
                    
                    # Show sent message preview
                    with st.expander("📨 Sent Message Preview"):
                        st.code(message, language=None)
                        
                except ValueError:
                    st.error("❌ Invalid Chat ID. Please enter a numeric Chat ID.")
                except Exception as e:
                    st.error(f"❌ Failed to send message: {str(e)}")
                    st.info("💡 Make sure your Chat ID is correct and the bot has been started in your Telegram chat.")
        
        # Instructions
        with st.expander("ℹ️ How to get your Chat ID"):
            st.markdown("""
            1. Start a chat with [@userinfobot](https://t.me/userinfobot) on Telegram
            2. Send any message to the bot
            3. The bot will reply with your Chat ID
            4. Copy the Chat ID and paste it above
            
            **Note:** Make sure to start a chat with your bot first by searching for it on Telegram and sending `/start`.
            """)