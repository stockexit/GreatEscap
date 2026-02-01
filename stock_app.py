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
# 1. 화면 설정 & 스타일
# =========================================================
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

st.markdown("""
<style>
    /* 탭 폰트 크기 */
    button[data-baseweb="tab"] div p { font-size: 18px !important; font-weight: bold !important; }
    
    /* 테이블 헤더 스타일 */
    thead tr th { background-color: #f5f6f7 !important; color: #333 !important; font-weight: bold !important; }
    
    /* 일반 메트릭 값 크기 */
    div[data-testid="stMetricValue"] { font-size: 26px !important; }
    
    /* 성장 모멘텀 등 녹색 배지(Delta) 커스텀 */
    div[data-testid="stMetricDelta"] {
        font-size: 22px !important;
        font-weight: bold !important;
        background-color: rgba(0, 200, 83, 0.2) !important;
        padding: 5px 15px !important;
        border-radius: 20px !important;
        width: fit-content !important;
    }
    div[data-testid="stMetricDelta"] svg { width: 20px !important; height: 20px !important; }
    
    /* 회사 개요 박스 스타일 */
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
# 2. 데이터 로딩 (구글 시트)
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
    except:
        return None

# =========================================================
# 3. 네이버 금융 크롤링 (한국 주식용) & 주식수 가져오기
# =========================================================
@st.cache_data(show_spinner=False)
def fetch_naver_summary(dart_code):
    """네이버 금융에서 기업 개요 크롤링"""
    try:
        url = f"https://finance.naver.com/item/main.naver?code={dart_code}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 네이버 금융 '기업개요' 섹션 찾기
        summary_info = soup.select_one('.summary_info')
        if summary_info:
            # FnGuide 요약 내용이 보통 여기에 있음
            descriptions = summary_info.find_all('p')
            full_text = " ".join([desc.get_text().strip() for desc in descriptions])
            return full_text
        return None
    except:
        return None

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
        
        df_merged['상장주식수'] = df_merged.apply(
            lambda x: x['시가총액'] / x['수정주가'] if x['수정주가'] > 0 else 0, axis=1
        )

        df_yearly = df_merged.groupby(df_merged.index.year).tail(1)
        df_yearly['연도'] = df_yearly.index.year.astype(str)
        result = df_yearly[['연도', '상장주식수', '시가총액']].reset_index(drop=True)
        
        return result
    except Exception as e:
        return pd.DataFrame()

# =========================================================
# 4. DART 재무제표 크롤링
# =========================================================
@st.cache_data(show_spinner=False) 
def fetch_core_financials(api_key, ticker_code):
    try:
        dart = OpenDartReader(api_key)
    except Exception as e:
         return None, None, f"API 키 오류: {e}"

    if len(str(ticker_code)) != 6:
        return None, None, "DART 조회 불가"

    now_year = datetime.datetime.now().year 
    years = range(now_year, now_year - 12, -1) 
    
    result_data = []
    
    try:
        for year in years:
            if len(result_data) >= 10: break
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
                    val_str = str(rows.iloc[0]['thstrm_amount']).replace(',', '').strip()
                    try: return float(val_str)
                    except: return 0

                df_cfs = df[df['fs_div'] == 'CFS']
                df_ofs = df[df['fs_div'] == 'OFS']
                sales = extract_value(df_cfs, mask_sales)
                op_income = extract_value(df_cfs, mask_op)
                net_income = extract_value(df_cfs, mask_net)

                if sales == 0: sales = extract_value(df_ofs, mask_sales)
                if op_income == 0: op_income = extract_value(df_ofs, mask_op)
                if net_income == 0: net_income = extract_value(df_ofs, mask_net)

                if sales != 0 or op_income != 0:
                    result_data.append({'연도': str(year), '매출액': sales, '영업이익': op_income, '순이익': net_income})
            time.sleep(0.05)

        if result_data:
            df_dart = pd.DataFrame(result_data)
            df_shares = fetch_shares_history(ticker_code)
            if not df_shares.empty:
                df_final = pd.merge(df_dart, df_shares, on='연도', how='left')
            else:
                df_final = df_dart
                df_final['상장주식수'] = 0
                df_final['시가총액'] = 0
            
            df_final = df_final.sort_values('연도', ascending=False)
            df_final['EPS(보정)'] = df_final.apply(lambda r: r['순이익']/r['상장주식수'] if r['상장주식수']>0 else 0, axis=1)
            df_final['EV/EBIT(배)'] = df_final.apply(lambda r: r['시가총액']/r['영업이익'] if r['영업이익']>0 else 0, axis=1)

            df_final['매출액(억)'] = (df_final['매출액'] / 100000000).round(0)
            df_final['영업이익(억)'] = (df_final['영업이익'] / 100000000).round(0)
            df_final['순이익(억)'] = (df_final['순이익'] / 100000000).round(0)
            df_final['시가총액(억)'] = (df_final['시가총액'] / 100000000).round(0)
            df_final['EPS(원)'] = df_final['EPS(보정)'].round(0)
            df_final['멀티플(배)'] = df_final['EV/EBIT(배)'].round(1)

            view_cols = ['연도', '매출액(억)', '영업이익(억)', '순이익(억)', '시가총액(억)', '멀티플(배)', 'EPS(원)']
            df_view = df_final[view_cols].set_index('연도').T
            return df_view, df_final.head(10), "OK"
        else:
            return None, None, "데이터 없음"
    except Exception as e:
        return None, None, f"오류: {e}"

# =========================================================
# 5. 차트 함수
# =========================================================
def draw_chart(ticker, period, title, unit, current_price=None, target_min=None, target_max=None, target_buy=None):
    try:
        interval = "1d" if period == "3mo" else "1wk"
        df = yf.download(ticker, period=period, interval=interval)
        if df.empty: return st.write(f"{title} 데이터 없음")
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name=title)])
        
        if current_price and current_price > 0:
            fig.add_hline(y=current_price, line_dash="dot", line_color="#FF4081", line_width=1)
            fig.add_annotation(xref="paper", x=0.5, y=current_price, text=f"<b>현재가 {unit}{current_price:,.0f}</b>", showarrow=False, xanchor="center", yshift=10, font=dict(color="white", size=14), bgcolor="#FF4081", bordercolor="white", borderwidth=1, opacity=0.9)

        if target_buy and target_buy > 0:
            fig.add_hline(y=target_buy, line_width=2, line_color="#FFFFFF", opacity=1.0)
            fig.add_annotation(xref="paper", x=0.5, y=target_buy, text=f"<b>⚡ 매수 {unit}{target_buy:,.0f}</b>", showarrow=False, yshift=0, xanchor="center", font=dict(color="black", size=14), bgcolor="#FFFFFF", bordercolor="gray", borderwidth=1, opacity=0.9)

        if target_min and target_min > 0:
            fig.add_hline(y=target_min, line_dash="dot", line_color="#00C853", opacity=0.8)
            fig.add_annotation(xref="paper", x=0.5, y=target_min, text=f"<b>🛡️ 보수 {unit}{target_min:,.0f}</b>", showarrow=False, yshift=-20, xanchor="center", font=dict(color="white", size=14), bgcolor="#00C853", bordercolor="white", borderwidth=1, opacity=0.9)

        if target_max and target_max > 0:
            fig.add_hline(y=target_max, line_dash="dash", line_color="#FF3D00", opacity=0.8)
            fig.add_annotation(xref="paper", x=0.5, y=target_max, text=f"<b>🚀 최대 {unit}{target_max:,.0f}</b>", showarrow=False, yshift=20, xanchor="center", font=dict(color="white", size=14), bgcolor="#FF3D00", bordercolor="white", borderwidth=1, opacity=0.9)
        
        fig.update_layout(title=dict(text=f"{title} ({unit})", font=dict(size=20)), height=450, template="plotly_dark", margin=dict(l=10, r=10, b=10, t=50), xaxis_rangeslider_visible=False, xaxis=dict(fixedrange=True), yaxis=dict(fixedrange=True))
        return st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})
    except Exception as e: return st.write(f"차트 에러: {e}")

# =========================================================
# 6. 메인 앱 로직
# =========================================================
df_sheet = load_data()

if df_sheet is not None:
    st.sidebar.markdown("## 🌍 시장 선택")
    market_choice = st.sidebar.radio("보고 싶은 시장", ["한국(KRW)", "미국(USD)"])
    if market_choice == "한국(KRW)":
        filtered_df = df_sheet[df_sheet['Market'] == "한국(KRW)"]
    else:
        filtered_df = df_sheet[df_sheet['Market'] == "미국(USD)"]
        
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"## 🎯 {market_choice} 종목")
    
    if not filtered_df.empty:
        selected = st.sidebar.selectbox("종목 선택 👇", filtered_df['종목명'].unique())
        s_info = filtered_df[filtered_df['종목명'] == selected].iloc[0]
        
        raw_code = str(s_info['코드']).strip().upper()
        if market_choice == "한국(KRW)":
            dart_code = "".join(re.findall(r'\d+', raw_code))
            if len(dart_code) < 6: dart_code = dart_code.zfill(6)
            yf_code = dart_code + ".KQ" if raw_code.endswith(".KQ") else dart_code + ".KS"
        else:
            dart_code = raw_code
            yf_code = raw_code

        is_korea = market_choice == "한국(KRW)"
        unit = "₩" if is_korea else "$"
        p_format = "{:,.0f}" if is_korea else "{:,.2f}"
        
        try:
            def clean_val(v):
                try: return float(str(v).replace(',', ''))
                except: return 0
            t_min = clean_val(s_info.get('보수적적정가', 0))
            t_max = clean_val(s_info.get('최대미래가치', 0))
            t_buy = clean_val(s_info.get('매수가치', 0))
            
            # yfinance 객체 (주가 데이터용)
            ticker_obj = yf.Ticker(yf_code)
            history = ticker_obj.history(period="1d")
            current_p = history['Close'].iloc[-1] if not history.empty else 0
            
            # [자동] 회사 개요 가져오기 & 문단 정리 로직
            # -----------------------------------------------
            summary_text = "회사 정보를 가져오는 중입니다..."
            source_label = ""
            
            try:
                # 1. 한국 주식이면 -> 네이버 금융 크롤링
                if is_korea:
                    naver_text = fetch_naver_summary(dart_code)
                    if naver_text:
                        raw_text = naver_text
                        source_label = "(네이버 금융)"
                    else:
                        # 네이버 실패시 yfinance 시도 (보통 한국껀 yfinance에 잘 없지만 백업용)
                        raw_text = ticker_obj.info.get('longBusinessSummary', '')
                        if raw_text: source_label = "(Yahoo - 번역)"
                
                # 2. 미국 주식이면 -> yfinance 사용
                else:
                    raw_text = ticker_obj.info.get('longBusinessSummary', '')
                    source_label = "(Yahoo - 번역)"

                # 3. 텍스트 가공 (번역 & 줄바꿈)
                if raw_text:
                    # 영문인 경우 번역 (한국어 포함 여부 간단 체크)
                    is_english = not re.search('[가-힣]', raw_text[:20]) 
                    if is_english:
                        translated_text = GoogleTranslator(source='auto', target='ko').translate(raw_text[:3000])
                    else:
                        translated_text = raw_text

                    # 문단 정리 (마침표 기준)
                    sentences = translated_text.split('. ')
                    formatted_text = ""
                    for i, sentence in enumerate(sentences):
                        clean_sentence = sentence.strip()
                        if not clean_sentence.endswith('.'):
                            clean_sentence += "."
                        formatted_text += clean_sentence + " "
                        
                        # 3문장마다 줄바꿈
                        if (i + 1) % 3 == 0:
                            formatted_text += "<br><br>"
                    
                    summary_text = formatted_text
                else:
                    summary_text = "제공된 회사 개요 정보가 없습니다."

            except Exception as e:
                summary_text = f"회사 개요를 불러오지 못했습니다. ({str(e)})"
            # -----------------------------------------------

            gap_min = ((t_min - current_p)/current_p)*100 if current_p else 0
            gap_max = ((t_max - current_p)/current_p)*100 if current_p else 0
            gap_buy = ((t_buy - current_p)/current_p)*100 if current_p else 0
            cagr_min = ((t_min/current_p)**(1/7)-1)*100 if current_p and t_min else 0
            cagr_max = ((t_max/current_p)**(1/7)-1)*100 if current_p and t_max else 0
            grade = s_info.get('투자등급', '미분류') 
            badge_color = {"코어": "#2962FF", "위성": "#FFAB00", "시가존": "#2E7D32"}.get(grade, "#616161")
            badge_icon = {"코어": "💎", "위성": "🛰️", "시가존": "🚬"}.get(grade, "❔")
            badge_text = {"코어": "코어 (주력 후보)", "위성": "위성 (모멘텀 후보)", "시가존": "시가존 (분할 매수)"}.get(grade, "미지정")
        except:
            current_p = 0; gap_min=gap_max=gap_buy=cagr_min=cagr_max=0
            summary_text = "데이터 없음"

        st.title(f"🚀 {selected} ({dart_code if is_korea else yf_code}) 기업 가치")
        tab1, tab2 = st.tabs(["🚀 종목 대시보드", "💎 가치분석 (매출/영업/EPS)"])

        with tab1:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("실시간 현재가", f"{unit}{p_format.format(current_p)}")
                st.markdown(f"""<div style="background-color: {badge_color}; padding: 5px 10px; border-radius: 5px; color: white; font-weight: bold;">{badge_icon} {badge_text}</div>""", unsafe_allow_html=True)
            with c2: st.metric("⚡ 매수 가치", f"{unit}{p_format.format(t_buy)}", f"{gap_buy:.1f}%")
            with c3: 
                st.metric("🛡️ 보수적 적정가", f"{unit}{p_format.format(t_min)}", f"{gap_min:.1f}%")
                if cagr_min: st.markdown(f"<div style='background-color:#7B1FA2;color:white;padding:8px;border-radius:5px;font-size:16px;font-weight:bold;'>📈 7~10년 CAGR {cagr_min:+.1f}%</div>", unsafe_allow_html=True)
            with c4: 
                st.metric("🚀 최대 미래가치", f"{unit}{p_format.format(t_max)}", f"{gap_max:.1f}%")
                if cagr_max: st.markdown(f"<div style='background-color:#7B1FA2;color:white;padding:8px;border-radius:5px;font-size:16px;font-weight:bold;'>📈 7~10년 CAGR {cagr_max:+.1f}%</div>", unsafe_allow_html=True)
            
            st.write("---")
            
            # [UI] 회사 개요 박스
            st.markdown(f"""
            <div class="summary-box" style="line-height: 1.8; text-align: justify; font-size: 15px;">
                <b style="font-size: 18px; color: #FFAB00;">🏢 {selected} 기업 개요</b> <span style="font-size: 12px; color: gray;">{source_label}</span><br><br>
                {summary_text}
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1: draw_chart(yf_code, "3mo", "📅 최근 3개월", unit, current_price=current_p)
            with col2: draw_chart(yf_code, "5y", "🏛️ 5년 장기", unit, current_price=None, target_min=t_min, target_max=t_max, target_buy=t_buy)
            
            st.subheader("📌 핵심 요약 (메모)")
            st.info(s_info.get('메모', '메모 없음'))
            
            st.subheader("💡 심층 리포트")
            note = s_info.get('노트링크', '')
            if note and "docs.google.com" in str(note):
                components.iframe(note.replace("/edit", "/preview"), height=800, scrolling=True)
            elif s_info.get('이미지URL'):
                st.image(s_info.get('이미지URL'), use_container_width=True)
                if str(note).startswith('http'): st.link_button("🔗 링크 열기", note)

        with tab2:
            if not is_korea:
                st.info("미국 주식은 지원하지 않습니다.")
            else:
                DART_API_KEY = "f7626661c1cd11987d285bd50b6d94ffdc08ca62" 
                with st.spinner(f"재무 데이터 통합 중... ({selected})"):
                    display_df, raw_data, msg = fetch_core_financials(DART_API_KEY, dart_code)
                
                if display_df is not None:
                    raw_data = raw_data.sort_values('연도')
                    eps_series = raw_data['EPS(원)']
                    eps_mean_10 = eps_series.mean()
                    eps_mean_5 = eps_series.tail(5).mean()
                    latest_eps = eps_series.iloc[-1]

                    latest_vs_10y_rate = ((latest_eps - eps_mean_10) / eps_mean_10) * 100 if eps_mean_10 > 0 else 0
                    momentum_avg = ((eps_mean_5 - eps_mean_10) / eps_mean_10) * 100 if eps_mean_10 > 0 else 0

                    df_max = raw_data
                    period_max = len(df_max)
                    label_max = f"{period_max}년 연평균(CAGR)" if period_max < 10 else "10년 연평균(CAGR)"
                    df_5 = raw_data.tail(5) if len(raw_data) >= 5 else raw_data

                    def calculate_cagr(df):
                        if len(df) < 2: return "데이터 부족"
                        start_eps = df['EPS(원)'].iloc[0]; end_eps = df['EPS(원)'].iloc[-1]; years = len(df)-1
                        if start_eps <= 0: return "계산 불가(적자)"
                        try:
                            cagr = (end_eps / start_eps) ** (1/years) - 1
                            return f"{cagr*100:+.1f}%"
                        except: return "계산 오류"
                    cagr_max_str = calculate_cagr(df_max); cagr_5_str = calculate_cagr(df_5)

                    c_t1, c_t2, c_t3 = st.columns(3)
                    with c_t1: st.metric("10년 평균 EPS", f"{eps_mean_10:,.0f}원")
                    with c_t2: st.metric("5년 평균 EPS", f"{eps_mean_5:,.0f}원")
                    with c_t3: st.metric("최신 EPS 성장률", "", delta=f"{latest_vs_10y_rate:+.1f}%")
                    
                    st.write("") 

                    c_b1, c_b2, c_b3 = st.columns(3)
                    with c_b1: st.metric(label_max, cagr_max_str)
                    with c_b2: st.metric("최근 5년 연평균", cagr_5_str)
                    with c_b3: st.metric("성장 모멘텀", "", delta=f"{momentum_avg:+.1f}%")
                    
                    st.write("---")

                    st.dataframe(display_df.style.format("{:,.0f}"), use_container_width=True)
                    
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    fig.add_trace(go.Bar(x=raw_data['연도'], y=raw_data['매출액(억)'], name='매출액(좌측)', marker_color='#90CAF9', opacity=0.6), secondary_y=False)
                    fig.add_trace(go.Bar(x=raw_data['연도'], y=raw_data['영업이익(억)'], name='영업이익(좌측)', marker_color='#2962FF'), secondary_y=False)
                    fig.add_trace(go.Scatter(x=raw_data['연도'], y=raw_data['EPS(원)'], name='EPS(보정됨)', mode='lines+markers+text', line=dict(color='#00E676', width=3), marker=dict(size=8, color='#00E676', symbol='diamond'), text=raw_data['EPS(원)'].apply(lambda x: f"{x:,.0f}"), textposition="top center", textfont=dict(color="white", size=11)), secondary_y=True)
                    fig.add_hline(y=eps_mean_10, line_dash="dash", line_color="#FFAB00", line_width=2, secondary_y=True, annotation_text=f"10년평균: {eps_mean_10:,.0f}", annotation_position="top left", annotation_font_color="#FFAB00")
                    fig.add_hline(y=eps_mean_5, line_dash="dot", line_color="#D500F9", line_width=2, secondary_y=True, annotation_text=f"5년평균: {eps_mean_5:,.0f}", annotation_position="bottom left", annotation_font_color="#D500F9")
                    fig.update_layout(title=f"{selected} 실적 성장 추이", template="plotly_dark", barmode='group', height=550, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                    fig.update_yaxes(title_text="금액 (억 원)", secondary_y=False, showgrid=True, gridcolor='rgba(255,255,255,0.1)')
                    fig.update_yaxes(title_text="EPS (원)", secondary_y=True, showgrid=False)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning(f"데이터를 가져오지 못했습니다. ({msg})")
    else:
        st.warning("종목 없음")
else:
    st.error("데이터 로딩 실패")
