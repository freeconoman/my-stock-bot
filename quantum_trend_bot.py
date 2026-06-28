import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Quantum Backtest Pro", layout="wide")
st.title("🤖 퀀텀 트렌드 봇 (데이터 보정 버전)")

def apply_indicators(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    df['MA60'] = df['Close'].rolling(window=60).mean()
    ema1 = df['Close'].ewm(span=9, adjust=False).mean()
    ema2 = ema1.ewm(span=9, adjust=False).mean()
    ema3 = ema2.ewm(span=9, adjust=False).mean()
    df['TRIX'] = (ema3 - ema3.shift(1)) / ema3.shift(1) * 10000
    df['TRIX_SIGNAL'] = df['TRIX'].rolling(window=9).mean()
    low_min = df['Low'].rolling(window=14).min()
    high_max = df['High'].rolling(window=14).max()
    df['STOCH_K'] = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['STOCH_D'] = df['STOCH_K'].rolling(window=3).mean()
    return df

def backtest_strategy(ticker, start_date_str, end_date_str):
    # ★ 수정: 90일 전부터 가져와서 지표를 충분히 예열함
    start_dt = pd.to_datetime(start_date_str) - timedelta(days=90)
    df = yf.download(ticker, start=start_dt.strftime('%Y-%m-%d'), end=end_date_str, progress=False)
    
    if len(df) < 120: return None
    
    df = apply_indicators(df)
    
    # ★ 수정: 지표 계산 후, 원래 요청한 기간(start_date)부터의 데이터만 추출
    df = df.loc[start_date_str:]
    
    buy_cond = (df['Close'] < df['MA60']) & \
               (df['STOCH_K'].shift(1) < df['STOCH_D'].shift(1)) & (df['STOCH_K'] > df['STOCH_D']) & \
               (df['TRIX'].shift(1) < df['TRIX_SIGNAL'].shift(1)) & (df['TRIX'] > df['TRIX_SIGNAL'])
    
    df['Signal'] = 0
    df.loc[buy_cond, 'Signal'] = 1
    
    trades = df[df['Signal'] == 1].copy()
    if trades.empty: return None
    
    # 5일 뒤 매도 수익률 (데이터 끝부분 체크)
    future_closes = df['Close'].shift(-5)
    trades['Entry_Price'] = trades['Close']
    trades['Exit_Price'] = future_closes.loc[trades.index]
    trades = trades.dropna(subset=['Exit_Price'])
    
    if trades.empty: return None
    
    trades['Return'] = (trades['Exit_Price'] - trades['Entry_Price']) / trades['Entry_Price']
    
    win_rate = (len(trades[trades['Return'] > 0]) / len(trades)) * 100
    pl_ratio = trades[trades['Return'] > 0]['Return'].mean() / abs(trades[trades['Return'] <= 0]['Return'].mean()) if len(trades[trades['Return'] <= 0]) > 0 else 0
    cum_ret = ((1 + trades['Return']).prod() - 1) * 100
    
    return win_rate, pl_ratio, cum_ret

# UI
ticker = st.sidebar.text_input("종목 코드", "005930.KS")
if st.sidebar.button("백테스팅 실행"):
    with st.spinner("분석 중..."):
        periods = {
            "최근 1년": (datetime.now() - timedelta(days=365), datetime.now()),
            "최근 3년": (datetime.now() - timedelta(days=365*3), datetime.now()),
            "최근 5년": (datetime.now() - timedelta(days=365*5), datetime.now()),
            "최근 10년": (datetime.now() - timedelta(days=365*10), datetime.now()),
            "2022.01~2025.03": ("2022-01-01", "2025-03-31")
        }
        
        results = []
        for name, (s, e) in periods.items():
            start_str = s.strftime('%Y-%m-%d') if isinstance(s, datetime) else s
            end_str = e.strftime('%Y-%m-%d') if isinstance(e, datetime) else e
            
            res = backtest_strategy(ticker, start_str, end_str)
            if res:
                results.append({"기간": name, "승률(%)": f"{res[0]:.2f}", "손익비": f"{res[1]:.2f}", "누적수익률(%)": f"{res[2]:.2f}"})
            else:
                results.append({"기간": name, "승률(%)": "신호없음", "손익비": "-", "누적수익률(%)": "-"})
        
        st.table(pd.DataFrame(results))
