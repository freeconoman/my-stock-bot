import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime, timedelta

st.set_page_config(page_title="Quantum Trend Bot Pro", layout="wide")
st.title("🤖 퀀텀 트렌드 봇 (백테스팅 내장 버전)")

# 1. 자체 계산 엔진 (Pandas-ta 의존성 제거)
def apply_indicators(df):
    # MA60
    df['MA60'] = df['Close'].rolling(window=60).mean()
    # TRIX
    ema1 = df['Close'].ewm(span=9, adjust=False).mean()
    ema2 = ema1.ewm(span=9, adjust=False).mean()
    ema3 = ema2.ewm(span=9, adjust=False).mean()
    df['TRIX'] = (ema3 - ema3.shift(1)) / ema3.shift(1) * 10000
    df['TRIX_SIGNAL'] = df['TRIX'].rolling(window=9).mean()
    # Stochastic
    low_min = df['Low'].rolling(window=14).min()
    high_max = df['High'].rolling(window=14).max()
    df['STOCH_K'] = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['STOCH_D'] = df['STOCH_K'].rolling(window=3).mean()
    return df

# 2. 백테스팅 로직
def backtest(ticker, start, end):
    df = yf.download(ticker, start=start, end=end, progress=False)
    if len(df) < 100: return None
    df = apply_indicators(df)
    
    # 전략: 약세장(Close < MA60) + 골든크로스 발생시 매수
    df['Signal'] = ((df['Close'] < df['MA60']) & 
                    (df['STOCH_K'].shift(1) < df['STOCH_D'].shift(1)) & (df['STOCH_K'] > df['STOCH_D']) &
                    (df['TRIX'].shift(1) < df['TRIX_SIGNAL'].shift(1)) & (df['TRIX'] > df['TRIX_SIGNAL'])).astype(int)
    
    trades = df[df['Signal'] == 1].copy()
    if trades.empty: return None
    
    trades['Returns'] = df['Close'].pct_change(5).shift(-5) # 5일 보유 수익률 가정
    
    win_rate = (len(trades[trades['Returns'] > 0]) / len(trades)) * 100
    pl_ratio = trades[trades['Returns'] > 0]['Returns'].mean() / abs(trades[trades['Returns'] <= 0]['Returns'].mean())
    cum_ret = (trades['Returns'] + 1).prod() - 1
    
    return win_rate, pl_ratio, cum_ret * 100

# UI 구성
ticker = st.sidebar.text_input("종목 코드", "005930.KS")
if st.sidebar.button("분석 및 백테스팅 시작"):
    with st.spinner("데이터 분석 중..."):
        # 1. 현재 상황 분석
        df_all = yf.download(ticker, period="1y", progress=False)
        df_all = apply_indicators(df_all)
        curr = df_all.iloc[-1]
        
        st.subheader("📊 현재 시장 진단")
        is_weak = curr['Close'] < curr['MA60']
        st.write(f"현재 60일선 위치: {'약세장(기법 유효)' if is_weak else '강세장(주의)'}")
        st.line_chart(df_all[['Close', 'MA60']].tail(120))
        
        # 2. 백테스팅 결과
        st.subheader("📈 기간별 백테스팅 성과")
        periods = {
            "최근 1년": (datetime.now() - timedelta(days=365), datetime.now()),
            "최근 3년": (datetime.now() - timedelta(days=365*3), datetime.now()),
            "최근 5년": (datetime.now() - timedelta(days=365*5), datetime.now()),
            "최근 10년": (datetime.now() - timedelta(days=365*10), datetime.now()),
            "2022.01~2025.03": ("2022-01-01", "2025-03-31")
        }
        
        results = []
        for name, (s, e) in periods.items():
            res = backtest(ticker, s.strftime('%Y-%m-%d') if isinstance(s, datetime) else s, 
                                  e.strftime('%Y-%m-%d') if isinstance(e, datetime) else e)
            if res:
                results.append({"기간": name, "승률(%)": f"{res[0]:.2f}", "손익비": f"{res[1]:.2f}", "누적수익률(%)": f"{res[2]:.2f}"})
            else:
                results.append({"기간": name, "승률(%)": "-", "손익비": "-", "누적수익률(%)": "-"})
        
        st.table(pd.DataFrame(results))
