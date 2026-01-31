import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정
st.set_page_config(page_title="사장님 투자 터미널", layout="wide")

# 2. 지저분한 로고 제거 CSS
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결 (사장님 시트 주소)
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

# 1분마다 새 데이터를 확인하도록 설정 (ttl=60)
@st.cache_data(ttl=60)
def load_data(csv_url):
    try:
        return pd.read_csv(csv_url)
    except:
        return None

df_sheet = load_data(url)

# 4. 종목 선택 및 데이터 가져오기
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.title("🎯 종목 리스트")
    # 시트의 '종목명' 열을 리스트로 만듬
    stock_names = df_sheet['종목명'].dropna().tolist()
    selected = st.sidebar.selectbox("보고 싶은 종목 선택", stock_names)
    
    # 선택한 종목의 데이터 한 줄 추출
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
else:
    st.error("구글 시트 데이터를 가져오지 못했습니다. 시트 내용을 확인해주세요!")
    st.stop()

# 5. 차트 그리기 함수
def draw_chart(ticker, period, title):
    interval = "1wk" if period == "5y" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    if df.empty: return st.write(f"{title}: 데이터 로드 실패")
    
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    fig.update_layout(title=title, height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# 6. 메인 화면 출력
st.title(f"🚀 {selected} ({s_info['코드']})")

col1, col2 = st.columns(2)
with col1:
    draw_chart(s_info['코드'], "3mo", "📅 최근 3개월 흐름")
with col2:
    draw_chart(s_info['코드'], "5y", "🏛️ 5년 장기 성장")

st.write("---")

# 7. 하단 리포트 (사장님이 시트에 적은 내용)
c1, c2 = st.columns([1, 2])
with c1:
    st.metric("사장님 목표 적정가", f"{s_info['적정가']}")
with c2:
    st.success(f"**💡 사장님 투자 메모:**\n\n{s_info['메모']}")
