import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd
import requests
from bs4 import BeautifulSoup
import urllib.parse

# 1. 웹 페이지 기본 설정
st.set_page_config(page_title="Quantum Trend Bot", layout="wide", page_icon="🤖")
st.title("🤖 퀀텀 트렌드 봇 (TRIX & 스토캐스틱 실전 모델)")
st.caption("신창환 전문가의 약세장 역발상 추세 반전 기법 기반 시스템")

# 2. 사이드바 제어판 (데이터 부족 에러를 막기 위해 기간 선택 기능 제거)
st.sidebar.header("🕹️ 관제 센터")
target_ticker = st.sidebar.text_input("종목 코드 입력 (한국은 끝에 .KS 또는 .KQ)", "005930.KS")

# 3. 자체 구글 웹 검색 엔진
@st.cache_data(ttl=1800)
def google_web_search(ticker_name):
    search_query = f"{ticker_name} 주가 전망 호재 악재 뉴스"
    url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    search_urls = []
    
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        
        for a in soup.find_all("a", href=True):
            href = a['href']
            if href.startswith("http") and "google" not in href:
                if href not in search_urls:
                    search_urls.append(href)
            if len(search_urls) >= 4:
                break
    except Exception as e:
        return [f"검색 엔진 접근 지연 (사유: {e})"]
        
    return search_urls if search_urls else ["관련 최신 뉴스를 찾지 못했습니다."]

# 4. 주가 데이터 수집 및 기술적 지표 연산 (에러 원천 차단 버전)
@st.cache_data(ttl=3600)
def fetch_and_calculate_metrics(ticker):
    try:
        # yf.download 대신 yf.Ticker 구조 사용 (데이터 충돌 방지)
        stock = yf.Ticker(ticker)
        # 60일선 및 지표의 안정적인 계산을 위해 무조건 1년치(1y) 데이터 확보
        df = stock.history(period="1y")
        
        if df.empty:
            return None
            
        # 차트 에러를 일으키는 시간대(Timezone) 정보 삭제
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        # 60일 이동평균선
        df['MA60'] = df['Close'].rolling(window=60).mean()
        
        # TRIX 계산
        df.ta.trix(length=9, append=True)
        trix_col = [col for col in df.columns if 'TRIX' in col]
        
        if trix_col:
            df['TRIX_MAIN'] = df[trix_col[0]]
            df['TRIX_SIGNAL'] = df['TRIX_MAIN'].rolling(window=9).mean()
            
        # 스토캐스틱 계산
        df.ta.stoch(append=True)
        
        return df
    except Exception as e:
        return None

# 데이터 로드
stock_df = fetch_and_calculate_metrics(target_ticker)

# 5. 메인 대시보드 출력
if stock_df is not None:
    # 60일선 계산을 위해 소모된 앞부분의 빈 데이터(NaN)를 삭제
    stock_df = stock_df.dropna(subset=['TRIX_MAIN', 'MA60']) 
    
    # ★ 에러 방지: 데이터가 최소 2일(어제/오늘) 이상 남아있는지 최종 확인
    if len(stock_df) >= 2:
        curr_data = stock_df.iloc[-1]
        prev_data = stock_df.iloc[-2]
        
        # 스토캐스틱 컬럼을 안전하게 찾기
        stoch_k_cols = [c for c in stock_df.columns if 'STOCHk' in c]
        stoch_d_cols = [c for c in stock_df.columns if 'STOCHd' in c]
        
        if stoch_k_cols and stoch_d_cols:
            stoch_k_col = stoch_k_cols[0]
            stoch_d_col = stoch_d_cols[0]
            
            curr_close = float(curr_data['Close'])
            curr_ma60 = float(curr_data['MA60'])
            
            is_weak_market = curr_close < curr_ma60  
            
            stoch_golden = (prev_data[stoch_k_col] < prev_data[stoch_d_col]) and (curr_data[stoch_k_col] > curr_data[stoch_d_col])
            trix_golden = (prev_data['TRIX_MAIN'] < prev_data['TRIX_SIGNAL']) and (curr_data['TRIX_MAIN'] > curr_data['TRIX_SIGNAL'])

            # 화면 레이아웃
            layout_left, layout_right = st.columns([2, 1])
            
            with layout_left:
                st.subheader("📈 가격 흐름 및 60일 이동평균선 (최근 6개월)")
                # 화면에는 너무 길지 않게 최근 120일(약 6개월) 차트만 출력
                st.line_chart(stock_df[['Close', 'MA60']].tail(120))
                
                st.write("📊 **주요 지표 상세 데이터 (최근 3일)**")
                st.dataframe(stock_df[['Close', 'MA60', 'TRIX_MAIN', 'TRIX_SIGNAL', stoch_k_col]].tail(3))

            with layout_right:
                st.subheader("🎯 전략 판정 센터")
                
                if is_weak_market:
                    st.error("⚠️ [약세장 상태] 60일선 아래 위치")
                    st.caption("기법 적용 구간입니다. 지표 정렬을 확인합니다.")
                    st.markdown("---")
                    
                    if trix_golden and (stock_df[stoch_k_col].tail(3).max() > stock_df[stoch_d_col].tail(3).max()):
                        st.success("🔥 **[STRONG BUY] 강력 매수 신호!**\n\n스토캐스틱 상승과 TRIX 골든크로스가 완성되었습니다.")
                    elif stoch_golden:
                        st.warning("⏳ **[예비 신호 발생]**\n\n스토캐스틱 골든크로스 완료. TRIX 시그널 돌파를 대기하세요.")
                    else:
                        st.info("💤 **[관망] 진입 조건 미충족**")
                else:
                    st.info("☀️ [강세장 상태] 60일선 위 위치")
                    st.caption("신창환 기법은 약세장 전용이므로 현재 구간은 적용하지 않습니다.")
                    
                st.markdown("---")
                
                st.subheader("🌐 관련 실시간 뉴스 분석")
                with st.spinner("최신 이슈를 검색 중입니다..."):
                    web_feeds = google_web_search(target_ticker)
                    for feed in web_feeds:
                        if feed.startswith("http"):
                            st.markdown(f"🔗 [관련 뉴스 및 종목 리포트 보기]({feed})")
                        else:
                            st.caption(feed)
        else:
            st.error("지표 계산에 필요한 데이터가 부족합니다.")
    else:
        st.error("비교할 과거 데이터가 부족합니다.")
else:
    st.error("데이터를 정상적으로 불러오지 못했습니다. 종목 코드가 올바른지 확인해 주세요. (예: 005930.KS)")
