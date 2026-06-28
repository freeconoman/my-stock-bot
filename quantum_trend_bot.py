import streamlit as st
import yfinance as yf
import pandas_ta as ta
from googlesearch import search
import pandas as pd

# 1. 웹 페이지 기본 레이아웃 구성
st.set_page_config(page_title="Quantum Trend Bot", layout="wide")
st.title("🤖 퀀텀 트렌드 봇 (TRIX & 스토캐스틱 실전 모델)")
st.caption("신창환 전문가의 약세장 역발상 추세 반전 기법 기반 시스템")

# 2. 사이드바 제어판 (기존 코드명과 충돌 방지)
st.sidebar.header("🕹️ 관제 센터")
target_ticker = st.sidebar.text_input("종목 코드 입력 (샘플: 삼성전자)", "005930.KS")
lookback_period = st.sidebar.selectbox("데이터 조회 기간", ["3mo", "6mo", "1y"], index=1)

# 3. 실시간 구글 웹 검색 엔진 (종목 뉴스 스크래핑)
@st.cache_data(ttl=1800) # 30분간 검색 결과 캐싱으로 속도 최적화
def google_web_search(ticker_name):
    search_query = f"{ticker_name} 주가 전망 호재 악재 뉴스"
    search_urls = []
    try:
        # 스트림릿 서버에서 안전하게 구글 검색결과 상위 4개 추출
        for url in search(search_query, num_results=4):
            search_urls.append(url)
    except Exception as e:
        return [f"검색 엔진 일시적 제한 (오류: {e})"]
    return search_urls

# 4. 주가 데이터 수집 및 기술적 지표 연산
@st.cache_data
def fetch_and_calculate_metrics(ticker, period):
    df = yf.download(ticker, period=period)
    if df.empty:
        return None
    
    # 60일 이동평균선 (약세장/강세장 판별 기준)
    df['MA60'] = df['Close'].rolling(window=60).mean()
    
    # TRIX (9일 평활) 및 시그널선 계산
    df.ta.trix(length=9, append=True)
    # pandas-ta의 TRIX 결과 컬럼명 대응 (TRIX_9_15.0 형태로 생성됨)
    trix_col = [col for col in df.columns if 'TRIX' in col]
    if trix_col:
        df['TRIX_SIGNAL'] = df[trix_col[0]].rolling(window=9).mean()
        df['TRIX_MAIN'] = df[trix_col[0]]
        
    # 스토캐스틱 (Slow 14, 3, 3)
    df.ta.stoch(append=True)
    
    return df

# 데이터 로드
stock_df = fetch_and_calculate_metrics(target_ticker, lookback_period)

if stock_df is not None and 'TRIX_MAIN' in stock_df.columns:
    # 당일(curr) 및 전일(prev) 데이터 추출
    curr_data = stock_df.iloc[-1]
    prev_data = stock_df.iloc[-2]
    
    # 변수 평탄화 (Multi-index 대처용)
    curr_close = float(curr_data['Close'].iloc[0]) if isinstance(curr_data['Close'], pd.Series) else float(curr_data['Close'])
    curr_ma60 = float(curr_data['MA60'].iloc[0]) if isinstance(curr_data['MA60'], pd.Series) else float(curr_data['MA60'])
    
    # 5. 핵심 기법 조건 검증 (신창환의 선행/후행 필터)
    is_weak_market = curr_close < curr_ma60  # 60일선 아래 (약세장 체크)
    
    # 스토캐스틱 골든크로스 여부
    stoch_k_col = [c for c in stock_df.columns if 'STOCHk' in c][0]
    stoch_d_col = [c for c in stock_df.columns if 'STOCHd' in c][0]
    stoch_golden = (prev_data[stoch_k_col] < prev_data[stoch_d_col]) and (curr_data[stoch_k_col] > curr_data[stoch_d_col])
    
    # TRIX 시그널 돌파 여부
    trix_golden = (prev_data['TRIX_MAIN'] < prev_data['TRIX_SIGNAL']) and (curr_data['TRIX_MAIN'] > curr_data['TRIX_SIGNAL'])

    # 6. 화면 대시보드 레이아웃 구현
    layout_left, layout_right = st.columns([2, 1])
    
    with layout_left:
        st.subheader("📈 실시간 추세 및 지표 차트")
        # 차트 가시성을 위한 라인 구성
        chart_data = stock_df[['Close', 'MA60']].copy()
        st.line_chart(chart_data)
        
        st.write("📊 **보조지표 현황 (최근 3일)**")
        st.dataframe(stock_df[['Close', 'MA60', 'TRIX_MAIN', stoch_k_col]].tail(3))

    with layout_right:
        st.subheader("🎯 전략 판정 센터")
        
        # 시장 환경 브리핑
        if is_weak_market:
            st.error("⚠️ 현재 60일 이동평균선 아래: [약세장 상태]")
            st.caption("기법 적용 가능 상태입니다. 지표의 크로스 순서를 모니터링하세요.")
        else:
            st.info("☀️ 현재 60일 이동평균선 위: [강세장 상태]")
            st.caption("신창환 기법은 약세장 전용이므로 현재 구간에서는 신뢰도가 낮습니다.")
            
        st.markdown("---")
        
        # 매매 시그널 출력 엔진
        if is_weak_market:
            if trix_golden and (stock_df[stoch_k_col].tail(5).max() > stock_df[stoch_d_col].tail(5).max()):
                st.success("🔥 **[STRONG BUY] 강력 매수 신호 포착!**")
                st.balloons()
            elif stoch_golden:
                st.warning("⏳ **[예비 신호] 스토캐스틱 골든크로스 완료**")
                st.caption("TRIX가 시그널선을 뚫고 올라올 때까지 최종 진입을 대기하십시오.")
            else:
                st.info("💤 **[WAIT] 조건 미충족 (관망 상태)**")
        else:
            st.info("💤 **[WAIT] 조건 미충족 (관망 상태)**")
            
        st.markdown("---")
        
        # 실시간 웹 검색 기반 뉴스 연동 기능
        st.subheader("🌐 AI 웹 인텔리전스 (실시간 이슈)")
        with st.spinner("구글 실시간 트렌드 분석 중..."):
            web_feeds = google_web_search(target_ticker)
            for feed in web_feeds:
                if "http" in feed:
                    st.markdown(f"🔗 [실시간 정보 및 분석 링크]({feed})")
                else:
                    st.caption(feed)
else:
    st.error("유효하지 않은 종목 코드이거나 데이터를 불러오지 못했습니다. (확인: 한국 종목은 .KS 혹은 .KQ를 붙여야 합니다.)")