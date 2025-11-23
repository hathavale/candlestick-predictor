# app.py
import streamlit as st
import pandas as pd
import requests
from talib import abstract
from itertools import product
import numpy as np

st.title("Candlestick Predictor + MACD (Live & Backtest)")

API_KEY = st.secrets.get("ALPHA_VANTAGE_API_KEY", "demo")
ticker = st.text_input("Ticker", "AAPL").upper()
interval = st.selectbox("Time Interval", ["1min", "5min", "15min", "30min", "60min"], index=2)
include_extended = st.checkbox("Include After-Hours", value=True)

with st.expander("⚙️ Advanced Settings"):
    col1, col2, col3 = st.columns(3)
    with col1:
        use_rsi = st.checkbox("RSI (Momentum)", value=True, help="Identifies overbought/oversold conditions")
        use_macd = st.checkbox("MACD (Trend Momentum)", value=True, help="Measures momentum and trend strength")
    with col2:
        use_volume = st.checkbox("Volume Analysis", value=True, help="Confirms signals with volume spikes")
        use_trend = st.checkbox("Trend Filter (SMA)", value=True, help="Filters signals based on trend direction")
    with col3:
        use_cmf = st.checkbox("Chaikin Money Flow", value=False, help="Measures buying/selling pressure with volume")
        use_sar = st.checkbox("Parabolic SAR", value=False, help="Identifies potential reversal points")
    
    sensitivity = st.slider("Minimum Signal Strength", 3, 12, 6, help="Higher = fewer but stronger signals")

mode = st.radio("Mode", ["Live Prediction", "Backtest", "Optimize Indicators"], horizontal=True)

def calculate_score(row, df, use_rsi=True, use_macd=True, use_volume=True, use_trend=True, use_cmf=False, use_sar=False):
    score = 0
    signals = []

    # 1. Confirmed Candlestick Patterns
    try:
        if 'CDLENGULFING' in row and row['CDLENGULFING'] == 100 and row['close'] > row['open']:
            score += 5; signals.append("Bullish Engulfing (Confirmed)")
        if 'CDLENGULFING' in row and row['CDLENGULFING'] == -100 and row['close'] < row['open']:
            score -= 5; signals.append("Bearish Engulfing (Confirmed)")

        if 'CDLMORNINGSTAR' in row and row['CDLMORNINGSTAR'] == 100:
            if use_volume and 'volume_ratio' in row and row.get('volume_ratio', 1) > 1.2:
                score += 6; signals.append("Morning Star + Volume")
            else:
                score += 4; signals.append("Morning Star")
        if 'CDLEVENINGSTAR' in row and row['CDLEVENINGSTAR'] == -100:
            if use_volume and 'volume_ratio' in row and row.get('volume_ratio', 1) > 1.2:
                score -= 6; signals.append("Evening Star + Volume")
            else:
                score -= 4; signals.append("Evening Star")

        if 'CDLHAMMER' in row and row['CDLHAMMER'] == 100 and len(df) >= 6 and row['low'] == df['low'].iloc[-6:].min():
            score += 4; signals.append("Hammer at Swing Low")
    except (KeyError, TypeError):
        pass

    # 2. MACD Signals (Strongest momentum filter)
    try:
        if use_macd and 'MACD' in row and 'MACD_signal' in row and 'MACD_hist' in row:
            if not pd.isna(row['MACD']) and not pd.isna(row['MACD_signal']) and not pd.isna(row['MACD_hist']):
                macd = float(row['MACD'])
                signal = float(row['MACD_signal'])
                hist = float(row['MACD_hist'])
                prev_hist = float(df['MACD_hist'].iloc[-2]) if len(df) > 1 and 'MACD_hist' in df.columns else 0.0

                # Bullish MACD
                if macd > signal and hist > 0:
                    score += 4; signals.append("MACD Bullish")
                if macd > signal and hist > prev_hist and hist > 0:
                    score += 5; signals.append("MACD Momentum Surge")
                if macd > 0 and macd > signal and hist > 0:
                    score += 6; signals.append("MACD Above Zero (Strong Bull)")

                # Bearish MACD
                if macd < signal and hist < 0:
                    score -= 4; signals.append("MACD Bearish")
                if hist < prev_hist and hist < 0:
                    score -= 5; signals.append("MACD Momentum Fade")
                if macd < 0 and macd < signal and hist < 0:
                    score -= 6; signals.append("MACD Below Zero (Strong Bear)")
    except (ValueError, TypeError, KeyError):
        pass  # Skip MACD if data is invalid

    # 3. RSI Divergence + Volume Spike
    try:
        if use_rsi and 'RSI' in row and not pd.isna(row['RSI']) and 'RSI' in df.columns:
            rsi_val = float(row['RSI'])
            recent = df.iloc[-10:] if len(df) >= 10 else df
            if (len(recent) >= 3 and recent['close'].is_monotonic_decreasing and
                recent['RSI'].is_monotonic_increasing and rsi_val < 45):
                score += 7; signals.append("Bullish RSI Divergence")
            if (len(recent) >= 3 and recent['close'].is_monotonic_increasing and
                recent['RSI'].is_monotonic_decreasing and rsi_val > 55):
                score -= 7; signals.append("Bearish RSI Divergence")

        if use_volume and 'volume_ratio' in row and row.get('volume_ratio', 1) > 2.0:
            score += 3 if score > 0 else -3
            signals.append("Volume Explosion")
    except (KeyError, TypeError, ValueError):
        pass

    # 4. Trend Filter – Kill counter-trend noise
    try:
        if use_trend and 'SMA_20' in row and 'SMA_50' in row:
            if not pd.isna(row['SMA_20']) and not pd.isna(row['SMA_50']):
                if float(row['SMA_20']) > float(row['SMA_50']):
                    score = max(score, 0)  # Only bullish in uptrend
                    signals.append("Uptrend Filter")
                else:
                    score = min(score, 0)  # Only bearish in downtrend
                    signals.append("Downtrend Filter")
    except (KeyError, TypeError, ValueError):
        pass

    # 5. Chaikin Money Flow (CMF)
    try:
        if use_cmf and 'CMF' in row and not pd.isna(row['CMF']):
            cmf_val = float(row['CMF'])
            if cmf_val > 0.15:  # Strong buying pressure
                score += 4
                signals.append("CMF Strong Buy Pressure")
            elif cmf_val > 0.05:  # Moderate buying
                score += 2
                signals.append("CMF Buy Pressure")
            elif cmf_val < -0.15:  # Strong selling pressure
                score -= 4
                signals.append("CMF Strong Sell Pressure")
            elif cmf_val < -0.05:  # Moderate selling
                score -= 2
                signals.append("CMF Sell Pressure")
    except (KeyError, TypeError, ValueError):
        pass

    # 6. Parabolic SAR
    try:
        if use_sar and 'SAR' in row and not pd.isna(row['SAR']):
            sar_val = float(row['SAR'])
            close_val = float(row['close'])
            # SAR below price = bullish, SAR above price = bearish
            if sar_val < close_val:
                score += 3
                signals.append("SAR Bullish (Below Price)")
            else:
                score -= 3
                signals.append("SAR Bearish (Above Price)")
            
            # Check for SAR flip (reversal signal)
            if len(df) > 1 and 'SAR' in df.columns:
                prev_sar = float(df['SAR'].iloc[-2])
                prev_close = float(df['close'].iloc[-2])
                # Bullish flip: SAR was above, now below
                if prev_sar > prev_close and sar_val < close_val:
                    score += 5
                    signals.append("SAR Bullish Reversal")
                # Bearish flip: SAR was below, now above
                elif prev_sar < prev_close and sar_val > close_val:
                    score -= 5
                    signals.append("SAR Bearish Reversal")
    except (KeyError, TypeError, ValueError, IndexError):
        pass

    return score, signals

# ————— LIVE PREDICTION —————
if mode == "Live Prediction" and st.button("Predict"):
    with st.spinner("Fetching data..."):
        ext = "&extended_hours=true" if include_extended else ""
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={ticker}&interval={interval}&outputsize=compact&apikey={API_KEY}{ext}"
        data = requests.get(url).json()

        if "Error Message" in data:
            st.error(data["Error Message"])
        elif f"Time Series ({interval})" not in data:
            st.error("No data – check ticker/API key")
        else:
            df = pd.DataFrame([
                {"timestamp": t,
                 "open": float(v["1. open"]), "high": float(v["2. high"]),
                 "low": float(v["3. low"]), "close": float(v["4. close"]),
                 "volume": float(v["5. volume"])}
                for t, v in data[f"Time Series ({interval})"].items()
            ])
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)

            # Indicators
            for p in ['CDLDOJI','CDLHAMMER','CDLENGULFING','CDLMORNINGSTAR','CDLEVENINGSTAR',
                      'CDL3WHITESOLDIERS','CDL3BLACKCROWS','CDLHARAMI','CDLPIERCING','CDLDARKCLOUDCOVER']:
                df[p] = getattr(abstract, p)(df)

            if use_rsi:
                df['RSI'] = abstract.RSI(df, 14)
            
            if use_volume:
                df['volume_sma'] = df['volume'].rolling(20).mean()
                df['volume_ratio'] = df['volume'] / df['volume_sma']
            
            if use_macd:
                df['MACD'], df['MACD_signal'], df['MACD_hist'] = abstract.MACD(df)

            if use_trend:
                df['SMA_20'] = df['close'].rolling(20).mean()
                df['SMA_50'] = df['close'].rolling(50).mean()
            
            if use_cmf:
                df['CMF'] = abstract.ADOSC(df, fastperiod=3, slowperiod=10) / 1000000  # Normalize CMF
            
            if use_sar:
                df['SAR'] = abstract.SAR(df, acceleration=0.02, maximum=0.2)

            latest = df.iloc[-1]
            score, signals = calculate_score(latest, df, use_rsi, use_macd, use_volume, use_trend, use_cmf, use_sar)
            direction = "BULLISH" if score >= sensitivity else "BEARISH" if score <= -sensitivity else "NEUTRAL"
            color = "green" if direction == "BULLISH" else "red" if direction == "BEARISH" else "gray"

            session = "After Hours" if latest.name.hour < 9 or latest.name.hour >= 16 else "Regular Hours"
            st.markdown(f"### Next {interval} → **:{color}[{direction}]** ({session})")
            st.write("**Signals:**", ", ".join(signals) or "None")
            st.write(f"**Signal Strength:** {score}")

# ————— BACKTEST —————
elif mode == "Backtest" and st.button("Run Backtest"):
    with st.spinner("Running full backtest..."):
        ext = "&extended_hours=true" if include_extended else ""
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={ticker}&interval={interval}&outputsize=full&apikey={API_KEY}{ext}"
        data = requests.get(url).json()

        if "Error Message" in data or f"Time Series ({interval})" not in data:
            st.error("No data")
        else:
            df = pd.DataFrame([
                {"timestamp": t, "open": float(v["1. open"]), "high": float(v["2. high"]),
                 "low": float(v["3. low"]), "close": float(v["4. close"]), "volume": float(v["5. volume"])}
                for t, v in data[f"Time Series ({interval})"].items()
            ])
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)

            for p in ['CDLDOJI','CDLHAMMER','CDLENGULFING','CDLMORNINGSTAR','CDLEVENINGSTAR',
                      'CDL3WHITESOLDIERS','CDL3BLACKCROWS','CDLHARAMI','CDLPIERCING','CDLDARKCLOUDCOVER']:
                df[p] = getattr(abstract, p)(df)

            if use_rsi:
                df['RSI'] = abstract.RSI(df, 14)
            
            if use_volume:
                df['volume_sma'] = df['volume'].rolling(20).mean()
                df['volume_ratio'] = df['volume'] / df['volume_sma']
            
            if use_macd:
                df['MACD'], df['MACD_signal'], df['MACD_hist'] = abstract.MACD(df)

            if use_trend:
                df['SMA_20'] = df['close'].rolling(20).mean()
                df['SMA_50'] = df['close'].rolling(50).mean()
            
            if use_cmf:
                df['CMF'] = abstract.ADOSC(df, fastperiod=3, slowperiod=10) / 1000000  # Normalize CMF
            
            if use_sar:
                df['SAR'] = abstract.SAR(df, acceleration=0.02, maximum=0.2)

            correct = total = bull_c = bull_t = bear_c = bear_t = 0
            for i in range(60, len(df)-1):
                curr = df.iloc[i]
                past_df = df.iloc[:i+1]  # Only past data
                score, _ = calculate_score(curr, past_df, use_rsi, use_macd, use_volume, use_trend, use_cmf, use_sar)

                pred = "BULLISH" if score >= sensitivity else "BEARISH" if score <= -sensitivity else "NEUTRAL"
                if pred == "NEUTRAL": continue

                actual = "BULLISH" if df.iloc[i+1]['close'] > curr['close'] else "BEARISH"
                total += 1
                if pred == actual: correct += 1
                if pred == "BULLISH": bull_t += 1; bull_c += pred == actual
                else: bear_t += 1; bear_c += pred == actual

            acc = correct / total * 100 if total else 0
            st.markdown("### Backtest Results")
            st.write(f"**Accuracy: {acc:.1f}%** ({correct}/{total})")
            bull_acc = (bull_c/bull_t*100) if bull_t > 0 else 0
            bear_acc = (bear_c/bear_t*100) if bear_t > 0 else 0
            st.write(f"Bullish: {bull_c}/{bull_t} → {bull_acc:.1f}%")
            st.write(f"Bearish: {bear_c}/{bear_t} → {bear_acc:.1f}%")
            st.markdown("**Strong**" if acc >= 60 else "**Moderate**" if acc >= 54 else "**Weak**")

# ————— OPTIMIZE INDICATORS (Box-Behnken Design) —————
elif mode == "Optimize Indicators" and st.button("Find Optimal Combination"):
    with st.spinner("Running Box-Behnken optimization (27 experiments)..."):
        ext = "&extended_hours=true" if include_extended else ""
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={ticker}&interval={interval}&outputsize=full&apikey={API_KEY}{ext}"
        data = requests.get(url).json()

        if "Error Message" in data or f"Time Series ({interval})" not in data:
            st.error("No data")
        else:
            # Prepare data
            df = pd.DataFrame([
                {"timestamp": t, "open": float(v["1. open"]), "high": float(v["2. high"]),
                 "low": float(v["3. low"]), "close": float(v["4. close"]), "volume": float(v["5. volume"])}
                for t, v in data[f"Time Series ({interval})"].items()
            ])
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)

            # Calculate ALL indicators (always needed)
            for p in ['CDLDOJI','CDLHAMMER','CDLENGULFING','CDLMORNINGSTAR','CDLEVENINGSTAR',
                      'CDL3WHITESOLDIERS','CDL3BLACKCROWS','CDLHARAMI','CDLPIERCING','CDLDARKCLOUDCOVER']:
                df[p] = getattr(abstract, p)(df)
            
            df['RSI'] = abstract.RSI(df, 14)
            df['volume_sma'] = df['volume'].rolling(20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']
            df['MACD'], df['MACD_signal'], df['MACD_hist'] = abstract.MACD(df)
            df['SMA_20'] = df['close'].rolling(20).mean()
            df['SMA_50'] = df['close'].rolling(50).mean()
            df['CMF'] = abstract.ADOSC(df, fastperiod=3, slowperiod=10) / 1000000
            df['SAR'] = abstract.SAR(df, acceleration=0.02, maximum=0.2)

            # Box-Behnken Design for 6 factors (3 levels: -1, 0, 1 → False, N/A, True)
            # We use 0/1 coding where 0=False, 1=True for simplicity
            # Box-Behnken for 6 factors requires 54 runs, but we'll use a reduced fractional design
            # Simplified approach: Test center point + edge points + corner points strategically
            
            # Generate Box-Behnken-inspired design (27 runs covering main effects + interactions)
            experiments = [
                # Center point (run 3 times for stability)
                [1, 1, 1, 1, 0, 0],
                [1, 1, 1, 1, 0, 0],
                [1, 1, 1, 1, 0, 0],
                # Vary RSI + MACD
                [0, 0, 1, 1, 0, 0],
                [1, 1, 0, 0, 0, 0],
                [0, 1, 1, 0, 0, 0],
                [1, 0, 0, 1, 0, 0],
                # Vary Volume + Trend
                [1, 1, 0, 0, 0, 0],
                [1, 1, 1, 1, 0, 0],
                [0, 0, 1, 1, 0, 0],
                [0, 0, 0, 0, 0, 0],
                # Vary CMF + SAR
                [1, 1, 1, 1, 1, 0],
                [1, 1, 1, 1, 0, 1],
                [1, 1, 1, 1, 1, 1],
                [0, 0, 0, 0, 1, 1],
                # Mixed combinations
                [1, 0, 1, 0, 1, 0],
                [0, 1, 0, 1, 0, 1],
                [1, 1, 0, 0, 1, 1],
                [0, 0, 1, 1, 1, 1],
                [1, 0, 1, 1, 0, 1],
                [0, 1, 1, 0, 1, 0],
                # Edge cases
                [1, 1, 1, 0, 0, 0],
                [1, 1, 0, 1, 0, 0],
                [1, 0, 1, 1, 0, 0],
                [0, 1, 1, 1, 0, 0],
                [1, 1, 1, 1, 1, 0],
                [1, 1, 1, 1, 0, 1],
            ]

            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, exp in enumerate(experiments):
                rsi_flag, macd_flag, vol_flag, trend_flag, cmf_flag, sar_flag = exp
                
                status_text.text(f"Testing combination {idx+1}/27...")
                progress_bar.progress((idx + 1) / len(experiments))

                # Run backtest with this combination
                correct = total = 0
                for i in range(60, len(df)-1):
                    curr = df.iloc[i]
                    past_df = df.iloc[:i+1]
                    score, _ = calculate_score(curr, past_df, rsi_flag, macd_flag, vol_flag, trend_flag, cmf_flag, sar_flag)

                    pred = "BULLISH" if score >= sensitivity else "BEARISH" if score <= -sensitivity else "NEUTRAL"
                    if pred == "NEUTRAL": continue

                    actual = "BULLISH" if df.iloc[i+1]['close'] > curr['close'] else "BEARISH"
                    total += 1
                    if pred == actual: correct += 1

                acc = correct / total * 100 if total > 0 else 0
                results.append({
                    'RSI': bool(rsi_flag),
                    'MACD': bool(macd_flag),
                    'Volume': bool(vol_flag),
                    'Trend': bool(trend_flag),
                    'CMF': bool(cmf_flag),
                    'SAR': bool(sar_flag),
                    'Accuracy': acc,
                    'Total_Signals': total
                })

            progress_bar.empty()
            status_text.empty()

            # Find best combination
            results_df = pd.DataFrame(results)
            best_idx = results_df['Accuracy'].idxmax()
            best_config = results_df.iloc[best_idx]

            st.markdown("### 🎯 Optimal Indicator Configuration")
            st.markdown(f"**Best Accuracy: {best_config['Accuracy']:.2f}%** ({int(best_config['Total_Signals'])} signals tested)")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### ✅ Enable These:")
                if best_config['RSI']: st.write("✓ RSI (Momentum)")
                if best_config['MACD']: st.write("✓ MACD (Trend Momentum)")
                if best_config['Volume']: st.write("✓ Volume Analysis")
                if best_config['Trend']: st.write("✓ Trend Filter (SMA)")
                if best_config['CMF']: st.write("✓ Chaikin Money Flow")
                if best_config['SAR']: st.write("✓ Parabolic SAR")
            
            with col2:
                st.markdown("#### ❌ Disable These:")
                if not best_config['RSI']: st.write("✗ RSI (Momentum)")
                if not best_config['MACD']: st.write("✗ MACD (Trend Momentum)")
                if not best_config['Volume']: st.write("✗ Volume Analysis")
                if not best_config['Trend']: st.write("✗ Trend Filter (SMA)")
                if not best_config['CMF']: st.write("✗ Chaikin Money Flow")
                if not best_config['SAR']: st.write("✗ Parabolic SAR")

            # Show top 5 configurations
            st.markdown("### 📊 Top 5 Configurations Tested")
            top_5 = results_df.nlargest(5, 'Accuracy')[['RSI', 'MACD', 'Volume', 'Trend', 'CMF', 'SAR', 'Accuracy', 'Total_Signals']]
            top_5['Accuracy'] = top_5['Accuracy'].apply(lambda x: f"{x:.2f}%")
            st.dataframe(top_5, use_container_width=True)