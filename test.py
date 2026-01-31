import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정 (반드시 맨 처음에 와야 함)
st.set_page_config(page_title="사장님 주식 관제센터", layout="wide")

# 2. 데이터 관리 (사장님의 분석 저장소)
if 'db' not in st.session_state:
    st.session_state.db = {
        "삼성전자": {"코드": "005930.KS", "적정가": "95,000원", "메모": "반도체 업황 회복 및 AI 수요 증가로 실적 개선 기대"},
        "현대차": {"코드": "005380.KS", "적정가": "280,000원", "메모": "역대급 실적 지속 및 주주환원 정책 강화 기대"},
        "애플": {"코드": "AAPL", "적정가": "230달러", "메모": "AI 아이폰 출시로 인한 강력한 교체 주기 도래"}
    }

# 3. 비밀 관리자 모드 체크 (주소 뒤에 ?mode=sajang 입력 시만 활성화)
is_admin = st.query_params.get("mode") == "sajang"

# 4. 사이드바 구성 (종목 선택)
st.sidebar.header("🎯 분석 종목")
selected_name = st.sidebar.selectbox("리포트를 선택하세요", list(st.session_state.db.keys()))
stock_data = st.session_state.db[selected_name]

# 사장님(관리자) 전용 메뉴
if is_admin:
    st.sidebar.write("---")
    st.sidebar.warning("🛠️ 사장님 비밀 관리자 모드")
    with st.sidebar.form("admin_form"):
        new_name = st.text_input("새 종목 이름", "테슬라")
        new_code = st.text_input("종목 코드", "TSLA")
        new_price = st.text_input("나의 적정가", "300달러")
        new_memo = st.text_area("분석 내용", "자율주행 및 에너지 사업 확장")
        if st.form_submit_button("💾 데이터 저장"):
            st.session_state.db[new_name] = {"코드": new_code, "적정가": new_price, "메모": new_memo}
            st.rerun()

# 5. 차트 생성 함수 (오타 방지를 위해 완벽하게 구조화)
def draw_stock_chart(ticker, period, title):
    # 전체 역사는 주봉, 나머지는 일봉
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
        title=title, height=350, template="plotly_dark",
        xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, b=10, t=50),
        yaxis_type="log" if period == "max" else "linear"
    )
    return st.plotly_chart(fig, use_container_width=True)

# 6. 메인 화면: 2x2 차트 격자
st.title(f"🚀 {selected_name} 종합 분석 대시보드")

row1_col1, row1_col2 = st.columns(2)
with row1_col1:
    draw_stock_chart(stock_data["코드"], "1mo", "📅 단기 (1개월)")
with row1_col2:
    draw_stock_chart(stock_data["코드"], "3mo", "📅 분기 (3개월)")

row2_col1, row2_col2 = st.columns(2)
with row2_col1:
    draw_stock_chart(stock_data["코드"], "1y", "📅 중기 (1년)")
with row2_col2:
    draw_stock_chart(stock_data["코드"], "max", "🏛️ 전체 역사 (로그)")

st.write("---")

# 7. 메인 화면 하단: 사장님 가치평가 리포트
st.subheader(f"📑 {selected_name} 최종 가치평가 결론")
info_c1, info_c2 = st.columns([1, 3])

with info_c1:
    st.metric("사장님 적정가", stock_data["적정가"])

with info_c2:
    st.success(f"**💡 핵심 분석 요약:**\n\n{stock_data['메모']}")