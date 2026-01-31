import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl

# 1. 화면 설정 (반드시 코드 최상단에 위치)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. SSL 인증서 에러 방지
ssl._create_default_https_context = ssl._create_unverified_context

# 3. 데이터 로딩 및 시장 자동 분류
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
        url = sheet_url.split("/edit")[0] + "/export?format=csv"
        df = pd.read_csv(url)
        df = df.dropna(subset=['종목명'])
        
        # 종목 코드를 보고 한국(.KS, .KQ)과 미국 시장 분류
        df['Market'] = df['코드'].apply(
            lambda x: "한국(KRW)" if str(x).upper().endswith(('.KS', '.KQ')) else "미국(USD)"
        )
        return df
    except:
        return None

# 4. 차트 그리기 함수 (아이콘 제거 & 숫자 크기 30 이상 확대)
def draw_chart(ticker, period, title, unit, target_p=None):
    try:
        # [해결] 3개월은 일봉(1d), 5년은 주봉(1wk)으로 설정해 차트 중복 방지
        interval = "1d" if period == "3mo" else "1wk"
        df = yf.download(ticker, period=period, interval=interval)
        
        if df.empty:
            return st.write(f"{title} 데이터가 없습니다.")
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name=title
        )])
        
        # [핵심] 5년 차트에만 빨간 점선 + 큼직한 목표가 수치 표시 (아이콘 🎯 제거)
        if target_p:
            fig.add_hline(y=target_p, line_dash="dash", line_color="red")
            
            # 숫자
