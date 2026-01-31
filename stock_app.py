import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl

# 1. 화면 설정 (메뉴 상시 오픈)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. SSL 에러 방지
ssl._create_default_https_context = ssl._create_unverified_context

# 3. 데이터 로딩 및 시장 분류
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
        url = sheet_url.split("/edit")[0] + "/export?format=csv"
        df = pd.read_csv(url)
        df = df.dropna(subset=['종목명'])
        
        df['Market'] = df['코드'].apply(
            lambda x: "한국(KRW)" if str(x).upper().endswith(('.KS', '.KQ')) else "미국(USD)"
        )
        return df
    except:
        return None

# 4. 차트 그리기 함수 (목표가 라인 선택적 표시 기능)
def draw_chart(ticker, period, title, unit, target_p=None):
    try:
        interval = "1d" if period == "3mo" else "1wk"
        df = yf.download(ticker, period=period, interval=interval)
        
        if df.empty:
            return st.write(f"{title} 데이터를 찾을 수 없습니다.")
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name=title
        )])
        
        # [수정 핵심] target_p가 전달된 경우(5년 차트)에만 선을 긋습니다
        if target_p is not None:
            fig.add_hline(
                y=target_p, 
                line_dash="dash", 
                line_color="red", 
                annotation_text=f"사장님 목표가 ({unit}{target_p:,.0f})",
                annotation_position="top right"
            )
        
        fig.update_layout(
            title=dict(text=f"{title} ({unit})", font=dict(size=18)),
            height=450, template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, b=10, t=50),
            yaxis_type="log" if period == "5y" else "linear"
        )
        return st.plotly_chart(fig, use_container_width=True)
    except:
        return st.write("차트 로딩 중...")

# 5. 메인 로직 실행
df_sheet = load_data()

if df_sheet is not None:
    # 사이드바: 한국 시장 우선
    st.sidebar.markdown("## 🌍 시장 선택")
    market_choice = st.sidebar.radio("보고 싶은 시장을 골라주세요", ["한국(KRW)", "미국(USD)"])
    
    filtered_df = df_sheet[df_sheet['Market'] == market_choice]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"## 🎯 {market_choice} 종목")
    selected = st.sidebar.selectbox("종목 선택 👇", filtered_df['종목명'].unique())
    s_info = filtered_df[filtered_df['종목명'] == selected
