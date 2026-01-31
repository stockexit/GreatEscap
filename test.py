import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정 (가장 윗줄 고정)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" # 사이드바 메뉴가 처음부터 보이게 설정
)

# 2. 로고는 최소한으로만 숨깁니다 (에러 방지를 위해 안전한 방식 사용)
st.markdown("""
    <style>
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem !important;}
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결
# 사장님이 알려주신 시트 주소입니다
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

@st.cache_data(ttl=60) # 1분마다 자동 갱신
def load_data(csv_url):
    try:
        df = pd.read_csv(csv_url)
        return df.dropna(subset=['종목명'])
    except:
        return None

df_sheet = load_data(url)

# 4. 종목 선택 (왼쪽 사이드바 메뉴)
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.title("🎯 분석 종목 리스트")
    # 시트의 모든 종목명을 리스트로 가져옵니다
    stock_names = df_sheet['종목명'].unique().tolist()
    
    # 여기서 종목을 고르면 화면이 바뀝니다
    selected = st.sidebar.selectbox("종목을 골라주세요", stock_names)
    
    # 선택된 종목의 정보 추출
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
else:
    st.error("구글 시트를 읽지 못했습니다. 공유 설정을 확인해주세요!")
    st.stop()

# 5. 차트 그리기 함수 (SyntaxError 방지 완벽 검수)
def draw_chart(ticker, period, title):
    try:
        interval = "1wk" if period == "5y" else "1d"
        df = yf.download(ticker, period=period, interval=interval)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty:
            return st.write(f"⚠️ {title}: 데이터를 가져오지 못했습니다.")

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

# 7. 하단 리포트 (시트 내용 반영) [cite: image_e5
