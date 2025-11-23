# app.py
import streamlit as st
import pandas as pd
import requests
from talib import abstract

st.title("Candlestick Predictor (Regular + After Hours)")

API_KEY = st.secrets.get("ALPHA_VANTAGE_API_KEY", "demo")  # Use secrets.toml for real key
ticker = st.text_input("Ticker", "AAPL").upper()
interval = st.selectbox("Time Interval", ["1min", "5min", "15min", "30min", "60min"], index=2)
include_extended = st.checkbox("Include After-Hours Trading", value=True)

# Advanced settings
with st.expander("⚙️ Advanced Settings"):
    use_momentum = st.checkbox("Use RSI & Volume Momentum", value=True, help="Adds RSI and volume analysis for better context")
    use_trend = st.checkbox("Use Trend Analysis (SMA)", value=True, help="Adds Simple Moving Average trend detection")
    sensitivity = st.slider("Signal Threshold", 0, 5, 2, help="Lower = more signals but less confident. Higher = fewer but stronger signals")
    
# Mode selection
mode = st.radio("Mode", ["Live Prediction", "Backtest"], horizontal=True)

if mode == "Live Prediction" and st.button("Predict"):
    with st.spinner("Analyzing..."):
        # Add extended_hours parameter to include pre-market and after-hours data
        extended_param = "&extended_hours=true" if include_extended else ""
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={ticker}&interval={interval}&outputsize=compact&apikey={API_KEY}{extended_param}"
        resp = requests.get(url).json()
        
        if "Error Message" in resp:
            st.error(f"API Error: {resp['Error Message']}. Get free key at alphavantage.co")
        elif f"Time Series ({interval})" not in resp:
            st.error("Invalid ticker or no data. Try AAPL.")
        else:
            ts_key = f"Time Series ({interval})"
            ts = resp[ts_key]
            data = [{"timestamp": k, "open": v["1. open"], "high": v["2. high"], "low": v["3. low"], "close": v["4. close"], "volume": v["5. volume"]} for k, v in ts.items()]
            df = pd.DataFrame(data)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
            df = df.astype(float)
            df.sort_index(inplace=True)
            
            for p in ['CDLDOJI', 'CDLHAMMER', 'CDLENGULFING', 'CDLMORNINGSTAR', 'CDLEVENINGSTAR',
                      'CDL3WHITESOLDIERS', 'CDL3BLACKCROWS', 'CDLHARAMI', 'CDLPIERCING', 'CDLDARKCLOUDCOVER']:
                df[p] = getattr(abstract, p)(df)
            
            # Add momentum indicators
            if use_momentum:
                df['RSI'] = abstract.RSI(df, timeperiod=14)
                df['volume_sma'] = df['volume'].rolling(window=20).mean()
                df['volume_ratio'] = df['volume'] / df['volume_sma']
            
            # Add trend indicators
            if use_trend:
                df['SMA_20'] = df['close'].rolling(window=20).mean()
                df['SMA_50'] = df['close'].rolling(window=50).mean()
            
            latest = df.iloc[-1]
            latest_time = df.index[-1]
            
            score = 0
            signals = []
            
            # Determine if current candle is during after-hours
            hour = latest_time.hour
            is_after_hours = hour < 9 or hour >= 16  # Before 9:30 AM or after 4:00 PM ET
            market_session = "After Hours" if is_after_hours else "Regular Hours"
            
            # Log latest candlestick data and pattern values
            st.write("**Debug Info:**")
            st.write(f"Latest Candle Time: {latest_time.strftime('%Y-%m-%d %H:%M')} ({market_session})")
            st.write(f"Latest OHLC - Open: {latest['open']:.2f}, High: {latest['high']:.2f}, Low: {latest['low']:.2f}, Close: {latest['close']:.2f}")
            st.write(f"Pattern Values - CDLENGULFING: {latest['CDLENGULFING']}, CDLMORNINGSTAR: {latest['CDLMORNINGSTAR']}, CDLEVENINGSTAR: {latest['CDLEVENINGSTAR']}")
            st.write(f"CDLHAMMER: {latest['CDLHAMMER']}, CDLDOJI: {latest['CDLDOJI']}, CDL3WHITESOLDIERS: {latest['CDL3WHITESOLDIERS']}, CDL3BLACKCROWS: {latest['CDL3BLACKCROWS']}")
            st.write(f"CDLHARAMI: {latest['CDLHARAMI']}, CDLPIERCING: {latest['CDLPIERCING']}, CDLDARKCLOUDCOVER: {latest['CDLDARKCLOUDCOVER']}")
            st.write("---")
            
            # Candlestick pattern scoring
            if latest['CDLENGULFING'] == 100: score += 3; signals.append("Bullish Engulfing")
            if latest['CDLENGULFING'] == -100: score -= 3; signals.append("Bearish Engulfing")
            if latest['CDLMORNINGSTAR'] == 100: score += 4; signals.append("Morning Star")
            if latest['CDLEVENINGSTAR'] == -100: score -= 4; signals.append("Evening Star")
            if latest['CDLHAMMER'] == 100: score += 2; signals.append("Hammer")
            if latest['CDLDOJI'] == 100: score += 1; signals.append("Doji")
            if latest['CDL3WHITESOLDIERS'] == 100: score += 3; signals.append("Three White Soldiers")
            if latest['CDL3BLACKCROWS'] == -100: score -= 3; signals.append("Three Black Crows")
            if latest['CDLHARAMI'] == 100: score += 2; signals.append("Bullish Harami")
            if latest['CDLPIERCING'] == 100: score += 2; signals.append("Piercing Pattern")
            if latest['CDLDARKCLOUDCOVER'] == -100: score -= 2; signals.append("Dark Cloud Cover")
            
            # Add RSI momentum scoring
            if use_momentum and not pd.isna(latest['RSI']):
                if latest['RSI'] < 30: 
                    score += 2
                    signals.append("RSI Oversold")
                elif latest['RSI'] > 70: 
                    score -= 2
                    signals.append("RSI Overbought")
                
                # Volume confirmation
                if latest['volume_ratio'] > 1.5:  # High volume
                    if score > 0:
                        score += 1
                        signals.append("High Volume (Bullish)")
                    elif score < 0:
                        score -= 1
                        signals.append("High Volume (Bearish)")
            
            # Add trend analysis scoring
            if use_trend and not pd.isna(latest['SMA_20']) and not pd.isna(latest['SMA_50']):
                # Price above both MAs = uptrend
                if latest['close'] > latest['SMA_20'] and latest['close'] > latest['SMA_50']:
                    score += 2
                    signals.append("Uptrend (Above SMAs)")
                # Price below both MAs = downtrend
                elif latest['close'] < latest['SMA_20'] and latest['close'] < latest['SMA_50']:
                    score -= 2
                    signals.append("Downtrend (Below SMAs)")
                
                # Golden/Death cross
                if latest['SMA_20'] > latest['SMA_50']:
                    score += 1
                    signals.append("Golden Cross")
                elif latest['SMA_20'] < latest['SMA_50']:
                    score -= 1
                    signals.append("Death Cross")
            
            direction = "BULLISH" if score > sensitivity else "BEARISH" if score < -sensitivity else "NEUTRAL"
            color = "green" if direction=="BULLISH" else "red" if direction=="BEARISH" else "gray"
            
            # Note about after-hours volatility
            volatility_note = ""
            if is_after_hours:
                volatility_note = " ⚠️ *Note: After-hours trading typically has lower volume and higher volatility*"
            
            st.markdown(f"### Next {interval} ({market_session}) → **:{color}[{direction}]**{volatility_note}")
            st.write("Patterns:", ", ".join(signals) or "None")
            st.write(f"Signal strength: {score}")

elif mode == "Backtest" and st.button("Run Backtest"):
    with st.spinner("Running backtest..."):
        # Use full outputsize for backtesting
        extended_param = "&extended_hours=true" if include_extended else ""
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={ticker}&interval={interval}&outputsize=full&apikey={API_KEY}{extended_param}"
        resp = requests.get(url).json()
        
        if "Error Message" in resp:
            st.error(f"API Error: {resp['Error Message']}. Get free key at alphavantage.co")
        elif f"Time Series ({interval})" not in resp:
            st.error("Invalid ticker or no data. Try AAPL.")
        else:
            ts_key = f"Time Series ({interval})"
            ts = resp[ts_key]
            data = [{"timestamp": k, "open": v["1. open"], "high": v["2. high"], "low": v["3. low"], "close": v["4. close"], "volume": v["5. volume"]} for k, v in ts.items()]
            df = pd.DataFrame(data)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
            df = df.astype(float)
            df.sort_index(inplace=True)
            
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

# Deploy:
# pip install streamlit pandas requests ta-lib
# streamlit run app.py
# Free key: alphavantage.co (25 calls/day; premium for realtime)