import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정 (가장 윗줄 고정)
st.set_page_config(page_title="사장님 투자 터미널", layout="wide")

# 2. [수정됨] 메뉴는 살리고 지저분한 로고만 가리는 CSS
st.markdown("""
    <style>
    /* 상단 검은 바와 로고만 제거 */
    header[data-testid="stHeader"] {display: none !important;}
    footer {display: none !important;}
    
    /* 사이드바(메뉴)는 가리지 않고 배경색만 깔끔하게 유지 */
    [data-testid="stSidebar"] {background-color: #111111;}
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결
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

# 4. 종목 선택 (사이드바 메뉴)
if df_sheet is not None and not df_sheet.empty:
    # 시트의 모든 종목명을 가져옵니다
    stock_list = df_sheet['종목명'].unique().tolist()
    
    st.sidebar.title("🎯 분석 종목")
    # 여기서 종목을 선택하면 메인 화면이 바뀝니다!
    selected = st.sidebar.selectbox("종목을 골라보세요", stock_list)
    
    # 선택된 종목의 한 줄 데이터 추출
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
else:
    st.error("데이터를 가져올 수 없습니다.")
    st.stop()

# 5. 차트 그리기 함수 (에러 방지 괄호 체크 완료)
def draw_chart(ticker, period, title):
    interval = "1wk" if period == "5y" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    if isinstance(df.columns, pd.MultiIndex): 
        df.columns = df.columns.get_level_values(0)
    
    if df.empty: return st.error(f"{title}: 데이터 로드 실패")
    
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    fig.update_layout(title=title, height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# 6. 메인 화면 구성
st.title(f"🚀 {selected} ({s_info['코드']})")

col1, col2 = st.columns(2)
with col1:
    draw_chart(s_info['코드'], "3mo", "📅 최근 3개월")
with col2:
    draw_chart(s_info['코드'], "5y", "🏛️ 5년 장기 성장")

st.write("---")

# 7. 하단 리포트 (시트 메모 반영)
c1, c2 = st.columns([1, 2])
with c1:
    st.metric("목표 적정가", f"{s_info['적정가']}")
with c2:
    st.success(f"**💡 투자 포인트:**\n\n{s_info['메모']}")
