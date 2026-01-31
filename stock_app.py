import streamlit as st
import streamlit.components.v1 as components 
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ssl
import OpenDartReader
import time
import datetime
import re
from pykrx import stock 

# =========================================================
# 1. 화면 설정 & 스타일 (유료 서비스 느낌의 세련된 UI)
# =========================================================
st.set_page_config(page_title="사장님 투자 터미널", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    button[data-baseweb="tab"] div p { font-size: 18px !important; font-weight: bold !important; }
    thead tr th { background-color: #f5f6f7 !important; color: #333 !important; font-weight: bold !important; }
    div[data-testid="stMetricValue"] { font-size: 28px !important; font-weight: bold !important; }
    /* 메트릭 간격 조정 */
    [data-testid="metric-container"] { border: 1px solid #333; padding: 15px; border-radius: 10px; background-color: #1e1e1e; }
</style>
""", unsafe_allow_html=True)

ssl._create_default_https_context = ssl._create_unverified_context

# =========================================================
# 2. 데이터 수집 엔진 (기존 로직 유지)
# =========================================================
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
        url = sheet_url.split("/edit")[0] + "/export?format=csv"
        df = pd.read_csv(url)
        df = df.dropna(subset=['종목명'])
        df['Market'] = df['코드'].apply(lambda x: "한국(KRW)" if str(x).upper().endswith(('.KS', '.KQ')) or str(x).isdigit() else "미국(USD)")
        return df
    except: return None

@st.cache_data(show_spinner=False)
def fetch_shares_history(ticker_code):
    try:
        now_year = datetime.datetime.now().year
        start_date = f"{now_year - 12}0101"
        end_date = datetime.datetime.now().strftime("%Y%m%d")
        df_cap = stock.get_market_cap_by_date(start_date, end_date, ticker_code)
        df_price = stock.get_market_ohlcv_by_date(start_date, end_date, ticker_code, adjusted=True)
        df_merged = pd.concat([df_cap['시가총액'], df_price['종가']], axis=1)
        df_merged.columns = ['시가총액', '수정주가']
        df_merged['상장주식수'] = df_merged.apply(lambda x: x['시가총액'] / x['수정주가'] if x['수정주가'] > 0 else 0, axis=1)
        df_yearly = df_merged.groupby(df_merged.index.year).tail(1)
        df_yearly['연도'] = df_yearly.index.year.astype(str)
        return df_yearly[['연도', '상장주식수', '시가총액']].reset_index(drop=True)
    except: return pd.DataFrame()

@st.cache_data(show_spinner=False) 
def fetch_core_financials(api_key, ticker_code):
    try:
        dart = OpenDartReader(api_key)
        now_year = datetime.datetime.now().year 
        result_data = []
        status_text = st.empty()
        for year in range(now_year, now_year - 12, -1):
            if len(result_data) >= 10: break
            status_text.text(f"🔍 {year}년 재무데이터 스캔...")
            df = None
            try: df = dart.finstate(ticker_code, year, reprt_code='11011')
            except: pass 
            if df is not None and not df.empty and 'account_nm' in df.columns:
                df['account_clean'] = df['account_nm'].astype(str).str.replace(' ', '').str.strip()
                mask_sales = df['account_clean'].str.contains('매출액|영업수익') & ~df['account_clean'].str.contains('원가|총이익|미실현')
                mask_op = df['account_clean'].str.contains('영업이익') & ~df['account_clean'].str.contains('기타|금융|관계|지분')
                mask_net = df['account_clean'].str.contains('당기순이익') & ~df['account_clean'].str.contains('포괄') & ~df['account_clean'].str.contains('비지배')
                def extract_value(dataframe, mask):
                    if dataframe.empty: return 0
                    rows = dataframe[mask]
                    if rows.empty: return 0
                    if len(rows) > 1 and '당기순이익' in str(mask):
                        p_row = rows[rows['account_clean'].str.contains('지배')]
                        if not p_row.empty: rows = p_row
                    try: return float(str(rows.iloc[0]['thstrm_amount']).replace(',', '').strip())
                    except: return 0
                df_cfs, df_ofs = df[df['fs_div'] == 'CFS'], df[df['fs_div'] == 'OFS']
                sales, op_income, net_income = extract_value(df_cfs, mask_sales), extract_value(df_cfs, mask_op), extract_value(df_cfs, mask_net)
                if sales == 0: sales = extract_value(df_ofs, mask_sales)
                if op_income == 0: op_income = extract_value(df_ofs, mask_op)
                if net_income == 0: net_income = extract_value(df_ofs, mask_net)
                if sales != 0 or op_income != 0:
                    result_data.append({'연도': str(year), '매출액': sales, '영업이익': op_income, '순이익': net_income})
            time.sleep(0.05)
        status_text.empty()
        if result_data:
            df_dart = pd.DataFrame(result_data)
            df_shares = fetch_shares_history(ticker_code)
            df_final = pd.merge(df_dart, df_shares, on='연도', how='left') if not df_shares.empty else df_dart
            df_final = df_final.sort_values('연도', ascending=False)
            df_final['EPS(보정)'] = df_final.apply(lambda r: r['순이익']/r['상장주식수'] if r.get('상장주식수', 0)>0 else 0, axis=1)
            df_final['EV/EBIT(배)'] = df_final.apply(lambda r: r['시가총액']/r['영업이익'] if r.get('영업이익', 0)>0 else 0, axis=1)
            df_final['매출액(억)'], df_final['영업이익(억)'], df_final['순이익(억)'] = (df_final['매출액']/1e8).round(0), (df_final['영업이익']/1e8).round(0), (df_final['순이익']/1e8).round(0)
            df_final['시가총액(억)'], df_final['EPS(원)'], df_final['멀티플(배)'] = (df_final['시가총액']/1e8).round(0), df_final['EPS(보정)'].round(0), df_final['EV/EBIT(배)'].round(1)
            view_cols = ['연도', '매출액(억)', '영업이익(억)', '순이익(억)', '시가총액(억)', '멀티플(배)', 'EPS(원)']
            return df_final[view_cols].set_index('연도').T, df_final, "OK"
        else: return None, None, "데이터 없음"
    except Exception as e: return None, None, f"오류: {e}"

# =========================================================
# 3. 메인 대시보드 UI
# =========================================================
df_sheet = load_data()
if df_sheet is not None:
    market_choice = st.sidebar.radio("시장 선택", ["한국(KRW)", "미국(USD)"])
    filtered_df = df_sheet[df_sheet['Market'] == market_choice]
    if not filtered_df.empty:
        selected = st.sidebar.selectbox("종목 선택", filtered_df['종목명'].unique())
        s_info = filtered_df[filtered_df['종목명'] == selected].iloc[0]
        raw_code = str(s_info['코드']).strip().upper()
        dart_code = "".join(re.findall(r'\d+', raw_code)).zfill(6) if market_choice == "한국(KRW)" else raw_code
        yf_code = (dart_code + (".KQ" if raw_code.endswith(".KQ") else ".KS")) if market_choice == "한국(KRW)" else raw_code
        unit, p_format = ("₩", "{:,.0f}") if market_choice == "한국(KRW)" else ("$", "{:,.2f}")
        try:
            t_min, t_max, t_buy = [float(str(s_info.get(k, 0)).replace(',', '')) for k in ['보수적적정가', '최대미래가치', '매수가치']]
            history = yf.Ticker(yf_code).history(period="1d")
            current_p = history['Close'].iloc[-1] if not history.empty else 0
        except: current_p = 0

        st.title(f"🚀 {selected} ({dart_code}) 가치 분석")
        tab1, tab2 = st.tabs(["🚀 종목 대시보드", "💎 실적 분석"])

        with tab1:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("실시간 현재가", f"{unit}{p_format.format(current_p)}")
            c2.metric("⚡ 매수 가치", f"{unit}{p_format.format(t_buy)}")
            c3.metric("🛡️ 보수적 적정가", f"{unit}{p_format.format(t_min)}")
            c4.metric("🚀 최대 미래가치", f"{unit}{p_format.format(t_max)}")
            
        with tab2:
            if market_choice == "한국(KRW)":
                DART_API_KEY = "f7626661c1cd11987d285bd50b6d94ffdc08ca62" 
                with st.spinner("재무 데이터를 수집 중입니다..."):
                    display_df, raw_data, msg = fetch_core_financials(DART_API_KEY, dart_code)
                
                if display_df is not None:
                    raw_data = raw_data.sort_values('연도')
                    eps = raw_data['EPS(원)']
                    m10, m5, lat = eps.mean(), eps.tail(5).mean(), eps.iloc[-1]
                    
                    # 지표 계산
                    vs10y = ((lat - m10) / m10 * 100) if m10 > 0 else 0
                    mavg = ((m5 - m10) / m10 * 100) if m10 > 0 else 0
                    
                    def get_cagr_val(d):
                        if len(d) < 2 or d['EPS(원)'].iloc[0] <= 0: return 0
                        return ((d['EPS(원)'].iloc[-1]/d['EPS(원)'].iloc[0])**(1/(len(d)-1))-1)*100

                    # -----------------------------------------------------
                    # [수정 영역] 번호, 라인 싹 없애고 '녹색 배지'만 강조
                    # -----------------------------------------------------
                    st.write("") # 상단 여백
                    col_a1, col_a2, col_a3 = st.columns(3)
                    col_a1.metric("10년 평균 EPS", f"{m10:,.0f}원")
                    col_a2.metric("5년 평균 EPS", f"{m5:,.0f}원")
                    # 메인 숫자를 없애고 delta(배지)에만 집중
                    col_a3.metric("최신 EPS 성장률 (vs 10년평균)", "", delta=f"{vs10y:+.1f}%")
                    
                    col_b1, col_b2, col_b3 = st.columns(3)
                    col_b1.metric(f"{len(raw_data)}년 연평균 성장 (CAGR)", f"{get_cagr_val(raw_data):+.1f}%")
                    col_b2.metric("최근 5년 연평균 성장", f"{get_cagr_val(raw_data.tail(5)):+.1f}%")
                    col_b3.metric("성장 모멘텀 (최근 vs 장기)", "", delta=f"{mavg:+.1f}%")
                    
                    st.write("---")
                    st.dataframe(display_df.style.format("{:,.0f}"), use_container_width=True)
                    
                    # 차트 (Bar + Line)
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    fig.add_trace(go.Bar(x=raw_data['연도'], y=raw_data['매출액(억)'], name='매출액', marker_color='#90CAF9', opacity=0.6), secondary_y=False)
                    fig.add_trace(go.Bar(x=raw_data['연도'], y=raw_data['영업이익(억)'], name='영업이익', marker_color='#2962FF'), secondary_y=False)
                    fig.add_trace(go.Scatter(x=raw_data['연도'], y=eps, name='EPS', mode='lines+markers+text', line=dict(color='#00E676', width=3), text=eps.apply(lambda x: f"{x:,.0f}"), textposition="top center"), secondary_y=True)
                    
                    fig.add_hline(y=m10, line_dash="dash", line_color="#FFAB00", secondary_y=True, annotation_text="10년 평균")
                    fig.add_hline(y=m5, line_dash="dot", line_color="#D500F9", secondary_y=True, annotation_text="5년 평균")
                    
                    fig.update_layout(template="plotly_dark", barmode='group', height=500, margin=dict(t=30, b=0))
                    st.plotly_chart(fig, use_container_width=True)
            else: st.info("미국 주식은 지원 예정입니다.")
