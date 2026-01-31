import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정
st.set_page_config(page_title="사장님 투자 터미널", layout="wide")

# 2. 불필요한 UI 제거
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결 (사장님의 시트 주소)
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

# 1분 간격 업데이트 (ttl=60)
@st.cache_data(ttl=60)
def load_data(csv_url):
    try:
        df = pd.read_csv(csv_url)
        # 종목명이 있는 데이터만 깨끗하게 정리
        return df.dropna(subset=['종목명'])
    except:
        return None

df_sheet = load_data(url)

# 4. 왼쪽 사이드바: 종목 선택 메뉴
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.title("🎯 분석 종목 리스트")
    
    # [핵심] 구글 시트의 '종목명' 열에 있는 모든 이름을 리스트로 가져옵니다.
    stock_list = df_sheet['종목명'].unique().tolist()
    
    # 여기서 종목을 선택하면 아래 화면이 바뀝니다.
    selected_name = st.sidebar.selectbox("종목을 선택하세요", stock_list)
    
    # 선택된 종목의 행(Row) 정보만 가져오기
    stock_info = df_sheet[df_sheet['종목명'] == selected_name].iloc[0]
    
    st.sidebar.write("---")
    st.sidebar.info("💡 모바일은 왼쪽 상단 '>' 버튼을 누르면 이 메뉴가 나옵니다!")
else:
    st.error("구글 시트를 읽지 못했습니다. 공유 설정을 확인해주세요!")
    st.stop()

# 5. 차트 그리기 함수
def draw_chart(ticker, period, title):
    interval = "1wk" if period == "5y" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    if df.empty: return st.error(f"{title}: 데이터를 가져오지 못했습니다.")

    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    fig.update_layout(title=title, height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# 6. 메인 화면 출력
st.title(f"🚀 {selected_name} ({stock_info['코드'].upper()})")

col1, col2 = st.columns(2)
with col1:
    draw_chart(stock_info['코드'], "3mo", "📅 최근 3개월 흐름")
with col2:
    draw_chart(stock_info['코드'], "5y", "🏛️ 5년 장기 성장")

st.write("---")

# 7. 하단 리포트 (사장님 메모 반영)
c1, c2 = st.columns([1, 2])
with c1:
    st.metric("사장님 목표 적정가", f"{stock_info['적정가']}")
with c2:
    st.success(f"**💡 분석 메모:**\n\n{stock_info['메모']}")
