import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정
st.set_page_config(page_title="사장님 투자 터미널", layout="wide")

# 2. 지저분한 요소 제거 및 사이드바 강조 CSS
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    /* 사이드바가 모바일에서 잘 보이도록 배경색 살짝 강조 */
    [data-testid="stSidebar"] {background-color: #111111;}
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결 (사장님 주소 고정)
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

@st.cache_data(ttl=60)
def load_data(csv_url):
    try:
        df = pd.read_csv(csv_url)
        return df
    except:
        return None

df_sheet = load_data(url)

# 4. 종목 선택 (사이드바)
if df_sheet is not None and not df_sheet.empty:
    # 시트의 '종목명' 열에서 리스트 추출
    stock_names = df_sheet['종목명'].dropna().tolist()
    
    st.sidebar.title("🎯 종목 리서치")
    st.sidebar.info("왼쪽 화살표(>)를 눌러 종목을 변경하세요!")
    # 여기서 종목을 고르면 화면이 바뀝니다
    selected = st.sidebar.selectbox("어떤 종목을 분석할까요?", stock_names)
    
    # 고른 종목의 행 데이터만 추출
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
else:
    st.error("구글 시트를 읽지 못했습니다. 공유 설정을 확인해주세요!")
    st.stop()

# 5. 차트 그리기 함수
def draw_chart(ticker, period, title):
    interval = "1wk" if period == "5y" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    if df.empty: return st.write(f"{title}: 티커({ticker})를 확인하세요.")
    
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    fig.update_layout(title=title, height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# 6. 메인 화면 출력
st.title(f"🚀 {selected} ({s_info['코드']})")

col1, col2 = st.columns(2)
with col1:
    draw_chart(s_info['코드'], "3mo", "📅 최근 3개월")
with col2:
    draw_chart(s_info['코드'], "5y", "🏛️ 5년 장기 (로그)")

st.write("---")

# 7. 하단 리포트 (시트 내용 반영)
c1, c2 = st.columns([1, 2])
with c1:
    st.metric("사장님 적정가", f"{s_info['적정가']}")
with c2:
    st.success(f"**💡 분석 의견:**\n\n{s_info['메모']}")
