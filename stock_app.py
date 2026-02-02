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
import requests
from bs4 import BeautifulSoup
from pykrx import stock 
from deep_translator import GoogleTranslator 

# =========================================================
# 1. 화면 설정 & 스타일 (기존 스타일 그대로)
# =========================================================
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

st.markdown("""
<style>
    button[data-baseweb="tab"] div p { font-size: 18px !important; font-weight: bold !important; }
    thead tr th { background-color: #f5f6f7 !important; color: #333 !important; font-weight: bold !important; }
    div[data-testid="stMetricValue"] { font-size: 26px !important; }
    
    div[data-testid="stMetricDelta"] {
        font-size: 22px !important;
        font-weight: bold !important;
        background-color: rgba(0, 200, 83, 0.2) !important;
        padding: 5px 15px !important;
        border-radius: 20px !important;
        width: fit-content !important;
    }
    div[data-testid="stMetricDelta"] svg { width: 20px !important; height: 20px !important; }
    
    .summary-box {
        background-color: #262730;
        padding: 25px;
        border-radius: 10px;
        border-left: 5px solid #FFAB00;
        margin-bottom: 25px;
        font-size: 16px;
        color: #E0E0E0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
</style>
""", unsafe_allow_html=True)

ssl._create_default_https_context = ssl._create_unverified_context

# =========================================================
# 2. 데이터 로딩 & 수집 함수 (기존 로직 100% 유지)
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
def fetch_naver_summary(dart_code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={dart_code}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        summary_info = soup.select_one('.summary_info')
        if summary_info:
            descriptions = summary_info.find_all('p')
            return " ".join([desc.get_text().strip() for desc in descriptions])
        return None
    except: return None

@st.cache_data(show_spinner=False)
def fetch_shares_history(ticker_code):
    try:
        now_year = datetime.datetime.now().year
        start_date, end_date = f"{now_year - 12}0101", datetime.datetime.now().strftime("%Y%m%d")
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
def fetch_core_financials_dart(api_key, ticker_code):
    try:
        dart = OpenDartReader(api_key)
        if len(str(ticker_code)) != 6: return None, "Code Error"
        now_year = datetime.datetime.now().year 
        years, result_data = range(now_year, now_year - 12, -1), []
        for year in years:
            if len(result_data) >= 10: break
            try:
                df = dart.finstate(ticker_code, year, reprt_code='11011') 
                if df is not None and not df.empty:
                    df['account_nm'] = df['account_nm'].astype(str).str.replace(' ', '').str.strip()
                    def get_val(nm_list):
                        temp = df[(df['fs_div']=='CFS') & (df['account_nm'].isin(nm_list))]
                        if temp.empty: temp = df[(df['fs_div']=='OFS') & (df['account_nm'].isin(nm_list))]
                        try: return float(str(temp.iloc[0]['thstrm_amount']).replace(',', ''))
                        except: return 0
                    sales = get_val(['매출액', '수익(매출액)', '영업수익'])
                    op = get_val(['영업이익', '영업이익(손실)'])
                    net = get_val(['당기순이익', '당기순이익(손실)'])
                    if sales != 0 or op != 0: result_data.append({'연도': str(year), '매출액': sales, '영업이익': op, '순이익': net})
            except: pass
            time.sleep(0.05)
        if result_data:
            df_dart = pd.DataFrame(result_data)
            df_shares = fetch_shares_history(ticker_code)
            df_final = pd.merge(df_dart, df_shares, on='연도', how='left') if not df_shares.empty else df_dart
            if '상장주식수' not in df_final.columns: df_final['상장주식수'] = 0
            df_final = df_final.sort_values('연도', ascending=False)
            df_final['매출액(억)'] = (df_final['매출액'] / 1e8).round(0)
            df_final['영업이익(억)'] = (df_final['영업이익'] / 1e8).round(0)
            df_final['순이익(억)'] = (df_final['순이익'] / 1e8).round(0)
            df_final['EPS(원)'] = df_final.apply(lambda r: r['순이익']/r['상장주식수'] if r.get('상장주식수',0)>0 else 0, axis=1).round(0)
            if '시가총액' in df_final.columns:
                df_final['시가총액(억)'] = (df_final['시가총액'] / 1e8).round(0)
                df_final['멀티플(배)'] = df_final.apply(lambda r: r['시가총액']/r['영업이익'] if r.get('영업이익',0)>0 else 0, axis=1).round(1)
            return df_final, "OK"
        return None, "No Data"
    except Exception as e: return None, str(e)

# =========================================================
# 3. 차트 함수 (기존 디자인 유지)
# =========================================================
def draw_chart(ticker, period, title, unit, current_price=None, target_min=None, target_max=None, target_buy=None):
    try:
        interval = "1d" if period == "3mo" else "1wk"
        df = yf.download(ticker, period=period, interval=interval)
        if df.empty: return st.write(f"{title} 데이터 없음")
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name=title)])
        if current_price:
            fig.add_hline(y=current_price, line_dash="dot", line_color="#FF4081", line_width=1)
            fig.add_annotation(xref="paper", x=0.5, y=current_price, text=f"<b>현재가 {unit}{current_price:,.0f}</b>", showarrow=False, xanchor="center", yshift=10, font=dict(color="white", size=14), bgcolor="#FF4081", bordercolor="white", borderwidth=1, opacity=0.9)
        if target_buy:
            fig.add_hline(y=target_buy, line_width=2, line_color="#FFFFFF")
            fig.add_annotation(xref="paper", x=0.5, y=target_buy, text=f"<b>⚡ 매수 {unit}{target_buy:,.0f}</b>", showarrow=False, xanchor="center", font=dict(color="black", size=14), bgcolor="#FFFFFF")
        if target_min:
            fig.add_hline(y=target_min, line_dash="dot", line_color="#00C853")
            fig.add_annotation(xref="paper", x=0.5, y=target_min, text=f"<b>🛡️ 보수 {unit}{target_min:,.0f}</b>", showarrow=False, yshift=-20, xanchor="center", font=dict(color="white", size=14), bgcolor="#00C853")
        if target_max:
            fig.add_hline(y=target_max, line_dash="dash", line_color="#FF3D00")
            fig.add_annotation(xref="paper", x=0.5, y=target_max, text=f"<b>🚀 최대 {unit}{target_max:,.0f}</b>", showarrow=False, yshift=20, xanchor="center", font=dict(color="white", size=14), bgcolor="#FF3D00")
        fig.update_layout(title=dict(text=f"{title} ({unit})", font=dict(size=20)), height=450, template="plotly_dark", margin=dict(l=10, r=10, b=10, t=50), xaxis_rangeslider_visible=False)
        return st.plotly_chart(fig, use_container_width=True)
    except: st.write("차트 에러")

# =========================================================
# 4. 메인 앱 로직 (시장 대시보드만 제거)
# =========================================================
df_sheet = load_data()

st.sidebar.title("사장님 투자 터미널")
# 메뉴 선택 라디오 버튼 제거 후 바로 시장 선택 노출
st.sidebar.markdown("---")

if df_sheet is not None:
    st.sidebar.markdown("## 🌍 시장 선택")
    market_choice = st.sidebar.radio("보고 싶은 시장", ["한국(KRW)", "미국(USD)"])
    filtered_df = df_sheet[df_sheet['Market'] == market_choice]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"## 🎯 {market_choice} 종목")
    
    if not filtered_df.empty:
        selected = st.sidebar.selectbox("종목 선택 👇", filtered_df['종목명'].unique())
        s_info = filtered_df[filtered_df['종목명'] == selected].iloc[0]
        
        # 코드 파싱
        raw_code = str(s_info['코드']).strip().upper()
        if market_choice == "한국(KRW)":
            dart_code = "".join(re.findall(r'\d+', raw_code)).zfill(6)
            yf_code = dart_code + (".KQ" if raw_code.endswith(".KQ") else ".KS")
        else:
            dart_code = yf_code = raw_code

        is_korea = (market_choice == "한국(KRW)")
        unit, p_format = ("₩", "{:,.0f}") if is_korea else ("$", "{:,.2f}")
        
        # 데이터 계산
        def clean_val(v):
            try: return float(str(v).replace(',', ''))
            except: return 0
        t_min, t_max, t_buy = clean_val(s_info.get('보수적적정가')), clean_val(s_info.get('최대미래가치')), clean_val(s_info.get('매수가치'))
        
        ticker_obj = yf.Ticker(yf_code)
        history = ticker_obj.history(period="1d")
        current_p = history['Close'].iloc[-1] if not history.empty else 0

        # 개요 로직
        summary_text, source_label = "정보 가져오는 중...", ""
        if is_korea:
            naver_text = fetch_naver_summary(dart_code)
            if naver_text: summary_text, source_label = naver_text, "(출처: 네이버 금융)"
            else: summary_text = ticker_obj.info.get('longBusinessSummary', '')
        else: summary_text = ticker_obj.info.get('longBusinessSummary', '')

        # 번역 및 포맷 (기존 로직 그대로)
        if summary_text:
            if not re.search('[가-힣]', str(summary_text)[:20]):
                summary_text = GoogleTranslator(source='auto', target='ko').translate(str(summary_text)[:3000])
            sentences = str(summary_text).split('. ')
            summary_text = "".join([s.strip() + ". " + ("<br><br>" if (i+1)%3==0 else "") for i, s in enumerate(sentences)])

        # 지표 계산
        gap_min = ((t_min - current_p)/current_p*100) if current_p else 0
        gap_max = ((t_max - current_p)/current_p*100) if current_p else 0
        gap_buy = ((t_buy - current_p)/current_p*100) if current_p else 0
        cagr_min = ((t_min/current_p)**(1/7)-1)*100 if (current_p and t_min > current_p) else 0
        cagr_max = ((t_max/current_p)**(1/7)-1)*100 if (current_p and t_max > current_p) else 0
        
        grade = s_info.get('투자등급', '미분류')
        badge_color = {"코어": "#2962FF", "위성": "#FFAB00", "시가존": "#2E7D32"}.get(grade, "#616161")
        badge_icon = {"코어": "💎", "위성": "🛰️", "시가존": "🚬"}.get(grade, "❔")
        
        port_status = str(s_info.get('포트상태', '')).strip()
        port_badge_html = f'<div style="margin-top: 5px; background-color: #00C853; padding: 5px 10px; border-radius: 5px; color: white; font-weight: bold; font-size: 0.9em;">💰 포트 편입중</div>' if '보유' in port_status or '편입' in port_status else ""

        # UI 출력
        st.title(f"🚀 {selected} ({dart_code if is_korea else yf_code}) 기업 가치")
        tab1, tab2 = st.tabs(["🚀 종목 대시보드", "💎 가치분석 (매출/영업/EPS)"])

        with tab1:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("실시간 현재가", f"{unit}{p_format.format(current_p)}")
                st.markdown(f'<div style="background-color: {badge_color}; padding: 5px 10px; border-radius: 5px; color: white; font-weight: bold;">{badge_icon} {grade}</div>{port_badge_html}', unsafe_allow_html=True)
            with c2: st.metric("⚡ 매수 가치", f"{unit}{p_format.format(t_buy)}", f"{gap_buy:.1f}%")
            with c3: 
                st.metric("🛡️ 보수적 적정가", f"{unit}{p_format.format(t_min)}", f"{gap_min:.1f}%")
                if cagr_min: st.markdown(f"<div style='background-color:#7B1FA2;color:white;padding:8px;border-radius:5px;font-size:16px;font-weight:bold;'>📈 7~10년 CAGR {cagr_min:+.1f}%</div>", unsafe_allow_html=True)
            with c4: 
                st.metric("🚀 최대 미래가치", f"{unit}{p_format.format(t_max)}", f"{gap_max:.1f}%")
                if cagr_max: st.markdown(f"<div style='background-color:#7B1FA2;color:white;padding:8px;border-radius:5px;font-size:16px;font-weight:bold;'>📈 7~10년 CAGR {cagr_max:+.1f}%</div>", unsafe_allow_html=True)
            
            st.write("---")
            st.markdown(f'<div class="summary-box"><b style="font-size: 18px; color: #FFAB00;">🏢 {selected} 기업 개요</b> <span style="font-size: 12px; color: gray;">{source_label}</span><br><br>{summary_text}</div>', unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1: draw_chart(yf_code, "3mo", "📅 최근 3개월", unit, current_price=current_p)
            with col2: draw_chart(yf_code, "5y", "🏛️ 5년 장기", unit, target_min=t_min, target_max=t_max, target_buy=t_buy)
            
            st.subheader("📌 핵심 요약 (메모)")
            st.info(s_info.get('메모', '메모 없음'))
            
            st.subheader("💡 심층 리포트")
            note = s_info.get('노트링크', '')
            if note and "docs.google.com" in str(note): components.iframe(note.replace("/edit", "/preview"), height=800, scrolling=True)
            elif s_info.get('이미지URL'): st.image(s_info.get('이미지URL'), use_container_width=True)

        with tab2:
            if not is_korea: st.info("미국 주식은 지원하지 않습니다.")
            else:
                DART_API_KEY = "f7626661c1cd11987d285bd50b6d94ffdc08ca62"
                with st.spinner("연간 데이터 분석 중..."):
                    display_df, msg = fetch_core_financials_dart(DART_API_KEY, dart_code)
                if display_df is not None:
                    raw_data = display_df.sort_values('연도')
                    eps_series = raw_data['EPS(원)']
                    eps_mean_10, eps_mean_5 = eps_series.mean(), eps_series.tail(5).mean()
                    latest_vs_10y = ((eps_series.iloc[-1] - eps_mean_10) / eps_mean_10 * 100) if eps_mean_10 > 0 else 0
                    
                    c_t1, c_t2, c_t3 = st.columns(3)
                    c_t1.metric("10년 평균 EPS", f"{eps_mean_10:,.0f}원")
                    c_t2.metric("5년 평균 EPS", f"{eps_mean_5:,.0f}원")
                    c_t3.metric("최신 EPS 성장률", "", delta=f"{latest_vs_10y:+.1f}%")
                    
                    st.markdown("### 📊 연간 실적 (10년)")
                    view_cols = [c for c in ['연도', '매출액(억)', '영업이익(억)', '순이익(억)', 'EPS(원)', '시가총액(억)', '멀티플(배)'] if c in display_df.columns]
                    st.dataframe(display_df[view_cols].set_index('연도').T.style.format("{:,.0f}"), use_container_width=True)
                    
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    fig.add_trace(go.Bar(x=raw_data['연도'], y=raw_data['매출액(억)'], name='매출액', marker_color='#90CAF9', opacity=0.6), secondary_y=False)
                    fig.add_trace(go.Bar(x=raw_data['연도'], y=raw_data['영업이익(억)'], name='영업이익', marker_color='#2962FF'), secondary_y=False)
                    fig.add_trace(go.Scatter(x=raw_data['연도'], y=raw_data['EPS(원)'], name='EPS', mode='lines+markers', line=dict(color='#00E676', width=3)), secondary_y=True)
                    fig.update_layout(title=f"{selected} 실적 추이", template="plotly_dark", height=550)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.warning(f"데이터 로딩 실패: {msg}")
else: st.error("데이터 로딩 실패")
