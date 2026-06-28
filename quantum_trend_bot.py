import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Quantum Backtest Pro", layout="wide")
st.title("🤖 퀀텀 트렌드 봇 (엄격한 백테스팅 엔진)")

# 1. 지표 계산 함수 (데이터 무결성 확보)
def apply_indicators(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # 지표 계산
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

# 2. 정확한 백테스팅 로직 (수익률 계산 수정)
def backtest_strategy(ticker, start, end):
    df = yf.download(ticker, start=start, end=end, progress=False)
    if len(df) < 100: return None
    df = apply_indicators(df)
    
    # 매수 신호 조건
    buy_cond = (df['Close'] < df['MA60']) & \
               (df['STOCH_K'].shift(1) < df['STOCH_D'].shift(1)) & (df['STOCH_K'] > df['STOCH_D']) & \
               (df['TRIX'].shift(1) < df['TRIX_SIGNAL'].shift(1)) & (df['TRIX'] > df['TRIX_SIGNAL'])
    
    df['Signal'] = 0
    df.loc[buy_cond, 'Signal'] = 1
    
    # 매수 신호가 발생한 날들의 데이터 추출
    trades = df[df['Signal'] == 1].copy()
    if trades.empty: return None
    
    # [수익률 계산 수정] 매수 가격(Close) 대비 5일 후 가격 수익률
    # shift(-5)를 사용하여 현재 신호 기준 5일 뒤 종가를 가져옴
    future_closes = df['Close'].shift(-5)
    trades['Entry_Price'] = trades['Close']
    trades['Exit_Price'] = future_closes.loc[trades.index]
    
    # 미래 데이터가 없는 경우(데이터 끝부분) 제거
    trades = trades.dropna(subset=['Exit_Price'])
    if trades.empty: return None
    
    trades['Return'] = (trades['Exit_Price'] - trades['Entry_Price']) / trades['Entry_Price']
    
    # 성과 지표 산출
    total_trades = len(trades)
    wins = trades[trades['Return'] > 0]
    losses = trades[trades['Return'] <= 0]
    
    win_rate = (len(wins) / total_trades) * 100
    pl_ratio = wins['Return'].mean() / abs(losses['Return'].mean()) if len(losses) > 0 and abs(losses['Return'].mean()) > 0 else 0
    cum_ret = ((1 + trades['Return']).prod() - 1) * 100
    
    return win_rate, pl_ratio, cum_ret

# 3. UI 및 실행
ticker = st.sidebar.text_input("종목 코드", "005930.KS")
if st.sidebar.button("백테스팅 실행"):
    with st.spinner("백테스팅 분석 중..."):
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
                results.append({"기간": name, "승률(%)": "-", "손익비": "-", "누적수익률(%)": "-"})
        
        st.subheader(f"📈 {ticker} 전략 성과 검증")
        st.table(pd.DataFrame(results))
        
        st.caption("※ 이 성과는 5일 보유 후 매도를 가정한 시뮬레이션입니다.")
