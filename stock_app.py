import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl

# 1. 화면 설정 (한국 시장을 최상단에 배치)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. SSL 인증서 에러 방지 (로컬 실행 시 필수)
ssl._create_default_https_context = ssl._create_unverified_context

# 3. 데이터 로딩 및 시장 자동 분류
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
        url = sheet_url.split("/edit")[0] + "/export?format=csv"
        df = pd.read_csv(url)
        df = df.dropna(subset=['종목명'])
        
        # 코드 끝자리를 보고 한국/미국 시장 자동 분류
        df['Market'] = df['코드'].apply(
            lambda x: "한국(KRW)" if str(x).upper().endswith(('.KS', '.KQ')) else "미국(USD)"
        )
        return df
    except:
        return None

# 4. 차트 그리기 함수 (아이콘 제거 & 숫자 크기 업그레이드)
def draw_chart(ticker, period, title, unit, target_p=None):
    try:
        # [해결] 3mo는 일봉(1d), 5y는 주봉(1wk)으로 설정해 기간 중복 문제 해결
        interval = "1d" if period == "3mo" else "1wk"
        df = yf.download(ticker, period=period, interval=interval)
        
        if df.empty:
            return st.write(f"{title} 데이터를 불러올 수 없습니다.")
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name=title
        )])
        
        # [수정] 5년 차트에만 목표가 숫자만 큼직하게 표시 (아이콘 제거)
        if target_p:
            fig.add_hline(y=target_p, line_dash="dash", line_color="red")
            fig.add_annotation(
                x=df.index[-1], y=target_p,
                text=f"{unit}{target_p:,.0f}", # 아이콘(🎯) 제거
                showarrow=False, yshift=15,
                font=dict(color="white", size=24, family="Arial Black"), # 글자 크기 대폭 확대
                bgcolor="red", bordercolor="red", borderpad=5, opacity=0.9
            )
        
        fig.update_layout(
            title=dict(text=f"{title} ({unit})", font=dict(size=18)),
            height=450, template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, b=10, t=50)
        )
        return st.plotly_chart(fig, use_container_width=True)
    except:
        return st.write("차트 로딩 중...")

# 5. 메인 로직 실행
df_sheet = load_data()

if df_sheet is not None:
    # 사이드바 설정 (한국 시장이 첫 번째)
    st.sidebar.markdown("## 🌍 시장 선택")
    market_choice = st.sidebar.radio("보고 싶은 시장", ["한국(KRW)", "미국(USD)"])
    
    filtered_df = df_sheet[df_sheet['Market'] == market_choice]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"## 🎯 {market_choice} 종목")
    selected = st.sidebar.selectbox("종목 선택 👇", filtered_df['종목명'].unique())
    
    # [수술] KeyError 및 괄호 누락 방지 로직
    s_info = filtered_df[filtered_df['종목명'] == selected].iloc[0]
    
    ticker_code = s_info['코드'].upper()
    is_korea = market_choice == "한국(KRW)"
    unit = "₩" if is_korea else "$"
    
    try:
        ticker_obj = yf.Ticker(ticker_code)
        current_p = ticker_obj.history(period="1d")['Close'].iloc[-1]
        target_p = float(s_info['적정가'])
        gap_percent = ((target_p - current_p) / current_p) * 100
    except:
        current_p, target_p, gap_percent = 0, 0, 0

    st.title(f"🚀 {selected} ({ticker_code})")
    
    # 상단 요약 지표 (SyntaxError 완벽 수술 버전)
    c1, c2
