# app.py
import yfinance as yf
from talib import abstract
import streamlit as st
import pandas as pd

st.title("15-Min Candlestick Predictor")

ticker = st.text_input("Ticker", "AAPL").upper()
if st.button("Predict"):
    with st.spinner("Analyzing..."):
        df = yf.download(ticker, period="5d", interval="15m")
        # Handle MultiIndex columns from yfinance and rename to lowercase for TA-Lib
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.columns = [col.lower() for col in df.columns]
        for p in ['CDLDOJI', 'CDLHAMMER', 'CDLENGULFING', 'CDLMORNINGSTAR', 'CDLEVENINGSTAR',
                  'CDL3WHITESOLDIERS', 'CDL3BLACKCROWS', 'CDLHARAMI', 'CDLPIERCING', 'CDLDARKCLOUDCOVER']:
            df[p] = getattr(abstract, p)(df)
        
        latest = df.iloc[-1]
        score = 0
        signals = []
        
        # Check for bullish patterns
        if latest['CDLENGULFING'] == 100:
            score += 3
            signals.append("Bullish Engulfing")
        # Check for bearish engulfing
        if latest['CDLENGULFING'] == -100:
            score -= 3
            signals.append("Bearish Engulfing")
        # Check for morning star
        if latest['CDLMORNINGSTAR'] == 100:
            score += 4
            signals.append("Morning Star")
        # Check for evening star
        if latest['CDLEVENINGSTAR'] == -100:
            score -= 4
            signals.append("Evening Star")
        # Check for hammer (bullish)
        if latest['CDLHAMMER'] == 100:
            score += 2
            signals.append("Hammer")
        # Check for doji (neutral to slightly bullish)
        if latest['CDLDOJI'] == 100:
            score += 1
            signals.append("Doji")
        # Check for three white soldiers
        if latest['CDL3WHITESOLDIERS'] == 100:
            score += 3
            signals.append("Three White Soldiers")
        # Check for three black crows
        if latest['CDL3BLACKCROWS'] == -100:
            score -= 3
            signals.append("Three Black Crows")
        # Check for bullish harami
        if latest['CDLHARAMI'] == 100:
            score += 2
            signals.append("Bullish Harami")
        # Check for piercing pattern
        if latest['CDLPIERCING'] == 100:
            score += 2
            signals.append("Piercing Pattern")
        # Check for dark cloud cover
        if latest['CDLDARKCLOUDCOVER'] == -100:
            score -= 2
            signals.append("Dark Cloud Cover")
        
        direction = "BULLISH" if score > 1 else "BEARISH" if score < -1 else "NEUTRAL"
        color = "green" if direction=="BULLISH" else "red" if direction=="BEARISH" else "gray"
        
        st.markdown(f"### Next 15 min → **:{color}[{direction}]**")
        st.write("Patterns:", ", ".join(signals) or "None")
        st.write(f"Signal strength: {score}")

# Deploy (one command):
# pip install streamlit yfinance ta-lib
# streamlit run app.py