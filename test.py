import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 화면 설정
st.set_page_config(page_title="사장님 투자 터미널", layout="wide")

# 2. 지저분한 UI 제거
st.markdown("""
    <style>
    header {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 데이터 로드
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

@st.cache_data(ttl=60)
def load_data(csv_url):
    try:
        df = pd.read_csv(csv_url)
        return df.dropna(subset=['종목명'])
    except:
        return None

df_sheet = load_data(url)

# 4. 종목 선택 (사이드바)
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.title("🎯 분석 종목 리스트")
    stock_names = df_sheet['종목명'].unique().tolist()
    selected = st.sidebar.selectbox("종목을 고르세요", stock_names)
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
else:
    st.error("구글 시트를 읽지 못했습니다. 공유 설정을 확인해주세요!")
    st.stop()

# 5. 차트 그리기 함수 (에러 완벽 방지 검수)
def draw_chart(ticker, period, title):
    try:
        interval = "1wk" if period == "5y" else "1d"
        df = yf.download(ticker, period=period, interval=interval)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty:
            return st.warning(f"⚠️ {title}: 데이터 없음")

        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name=title
        )])

        fig.update_layout(
            title=dict(text=title, font=dict(size=16)),
            height=450, 
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, b=10, t=50),
            yaxis_type="log" if period == "5y" else "linear"
        )
        return st.plotly_chart(fig, use_container_width=True)
    except:
        return st.write(f"⚠️ {title}: 로딩 에러")

# 6. 메인 화면 구성
st.title(f"🚀 {selected} ({s_info['코드'].upper()})")

# 차트 2개 집중 배치
col1, col2 = st.columns(2)
with col1:
    draw_chart(s_info['코드'], "3mo", "📅 최근 3개월 흐름")
with col2:
    draw_chart(s_info['코드'], "5y", "🏛️ 5년 장기 성장 (로그)")

st.write("---")

# 7. 하단 리포트 (시트 내용 반영)
c_a, c_b = st.columns([1, 2])
with c_a:
    st.metric("사장님 목표가", f"{s_info['적정가']}")
with c_b:
    st.success(f"**💡 분석 메모:**\n\n{s_info['메모']}")
