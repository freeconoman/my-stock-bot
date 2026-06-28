import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import urllib.parse

st.set_page_config(page_title="Quantum Trend Bot", layout="wide")
st.title("🤖 퀀텀 트렌드 봇 (최종 안정화 버전)")

# 자체 계산 엔진 (pandas-ta 미사용)
def calculate_indicators(df):
    # MA60
    df['MA60'] = df['Close'].rolling(window=60).mean()
    
    # TRIX 직접 계산 (EMA 3회 적용)
    ema1 = df['Close'].ewm(span=9, adjust=False).mean()
    ema2 = ema1.ewm(span=9, adjust=False).mean()
    ema3 = ema2.ewm(span=9, adjust=False).mean()
    df['TRIX'] = (ema3 - ema3.shift(1)) / ema3.shift(1) * 10000
    df['TRIX_SIGNAL'] = df['TRIX'].rolling(window=9).mean()
    
    # Stochastic 직접 계산
    low_min = df['Low'].rolling(window=14).min()
    high_max = df['High'].rolling(window=14).max()
    df['STOCH_K'] = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['STOCH_D'] = df['STOCH_K'].rolling(window=3).mean()
    return df

target_ticker = st.text_input("종목 코드 (예: 005930.KS)", "005930.KS")

if st.button("분석 실행"):
    with st.spinner("데이터 로딩 및 계산 중..."):
        stock = yf.Ticker(target_ticker)
        df = stock.history(period="1y")
        
        if not df.empty:
            df = calculate_indicators(df)
            df = df.dropna()
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            st.write(f"현재가: {curr['Close']:.2f}")
            st.line_chart(df[['Close', 'MA60']].tail(60))
            
            # 매매 조건 판정
            is_weak = curr['Close'] < curr['MA60']
            stoch_gc = (prev['STOCH_K'] < prev['STOCH_D']) and (curr['STOCH_K'] > curr['STOCH_D'])
            trix_gc = (prev['TRIX'] < prev['TRIX_SIGNAL']) and (curr['TRIX'] > curr['TRIX_SIGNAL'])
            
            if is_weak and stoch_gc and trix_gc:
                st.success("🔥 강력 매수 신호 (Strong Buy)")
            else:
                st.info("관망 상태 (Wait)")
        else:
            st.error("데이터를 가져올 수 없습니다.")
