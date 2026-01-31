import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정 (로고 숨기기 및 레이아웃 최적화)
st.set_page_config(
    page_title="사장님 전용 가치투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None 
    }
)

# 2. 유료 사이트 느낌을 주는 화면 세척 CSS
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}
    /* 배경색과 차트의 통일감을 위해 약간의 여백 조정 */
    .block-container {padding-top: 2rem; padding-bottom: 0rem;}
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결 (사장님의 시트 주소 자동 적용)
# 이미 주소를 알고 있으니 제가 직접 세팅해두었습니다.
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

@st.cache_data(ttl=60)
def load_data(csv_url):
    try:
        # 시트 데이터 읽기
        df = pd.read_csv(csv_url)
        return df
    except Exception as e:
        return None

df_sheet = load_data(url)

# 4. 사이드바: 종목 선택
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.markdown("### 🎯 분석 리포트 선택")
    # 시트의 '종목명' 열을 기반으로 리스트 생성
    stock_list = df_sheet['종목명'].dropna().unique().tolist()
    selected_name = st.sidebar.selectbox("종목을 선택하세요", stock_list)
    
    # 선택된 종목의 한 줄 데이터 추출
    stock_info = df_sheet[df_sheet['종목명'] == selected_name].iloc[0]
else:
    st.error("⚠️ 구글 시트 데이터를 가져올 수 없습니다. '공유' 설정이 '링크가 있는 모든 사용자'로 되어 있는지 확인해주세요!")
    st.stop()

# 5. 차트 생성 함수 (에러 방지용)
def draw_chart(ticker, period, title):
    interval = "1wk" if period == "max" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    if df.empty:
        return st.error(f"{title} 데이터를 가져오지 못했습니다.")

    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], 
        low=df['Low'], close=df['Close'], name=title
    )])

    fig.update_layout(
        title=title, height=380, template="plotly_dark",
        xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, b=10, t=50),
        yaxis_type="log" if period == "max" else "linear"
    )
    return st.plotly_chart(fig, use_container_width=True)

# 6. 메인 화면 구성
st.title(f"🚀 {selected_name} ({stock_info['코드']})")
st.markdown(f"**기준일자:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")

# 4분할 차트 레이아웃
row1_left, row1_right = st.columns(2)
with row1_left:
    draw_chart(stock_info['코드'], "1mo", "📅 단기 (1개월)")
with row1_right:
    draw_chart(stock_info['코드'], "3mo", "📅 분기 (3개월)")

row2_left, row2_right = st.columns(2)
with row2_left:
    draw_chart(stock_info['코드'], "1y", "📅 중기 (1년)")
with row2_right:
    draw_chart(stock_info['코드'], "max", "🏛️ 전체 역사 (로그)")

st.write("---")

# 7. 하단 가치평가 리포트
st.subheader(f"📑 {selected_name} 투자 인사이트")
info_col1, info_col2 = st.columns([1, 2])

with info_col1:
    st.metric("사장님 목표 적정가", f"{stock_info['적정가']}")

with info_col2:
    st.success(f"**💡 분석 메모**\n\n{stock_info['메모']}")

st.write("---")
st.caption("※ 본 시스템은 사장님 전용 금융 터미널입니다. 구글 시트를 수정하면 실시간 반영됩니다.")
