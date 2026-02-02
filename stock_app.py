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
from concurrent.futures import ThreadPoolExecutor, as_completed

# =========================================================
# 1. 화면 설정 & 스타일 (화이트 테마)
# =========================================================
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 화이트 톤 스타일 적용
st.markdown("""
<style>
    .main { background-color: #FFFFFF; }
    h1, h2, h3 { color: #333333 !important; }
    div[data-testid="stMetricValue"] { font-size: 24px !important; color: #333333 !important; }
    div[data-testid="stMetricDelta"] { font-size: 16px !important; }
    
    /* 탭 스타일 */
    button[data-baseweb="tab"] { background-color: white; border: 1px solid #ddd; }
    button[data-baseweb="tab"][aria-selected="true"] { background-color: #f0f2f6; border-color: #2962FF; color: #2962FF !important; }
    
    .info-box {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #2962FF;
        color: #555;
        font-size: 14px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

ssl._create_default_https_context = ssl._create_unverified_context

# =========================================================
# 2. 데이터 로딩 (기존 유지)
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
# 3. 개별 종목 분석 함수 (기존 유지)
# =========================================================
@st.cache_data(show_spinner=False)
def fetch_naver_summary(dart_code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={dart_code}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        summary_info = soup.select_one('.summary_info')
        if summary_info:
            descriptions = summary_info.find_all('p')
            full_text = " ".join([desc.get_text().strip() for desc in descriptions])
            return full_text
        return None
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
def fetch_core_financials_dart(api_key, ticker_code):
    try:
        dart = OpenDartReader(api_key)
    except: return None, "API Key Error"
    if len(str(ticker_code)) != 6: return None, "Code Error"
    now_year = datetime.datetime.now().year 
    years = range(now_year, now_year - 12, -1) 
    result_data = []
    try:
        for year in years:
            if len(result_data) >= 10: break
            try:
                df = dart.finstate(ticker_code, year, reprt_code='11011') 
                if df is not None and not df.empty:
                    df['account_nm'] = df['account_nm'].astype(str).str.replace(' ', '').str.strip()
                    def get_val(nm_list):
                        temp = df[(df['fs_div']=='CFS') & (df['account_nm'].isin(nm_list))]
                        if temp.empty: temp = df[(df['fs_div']=='OFS') & (df['account_nm'].isin(nm_list))]
                        if temp.empty: return 0
                        try:
                            val = temp.iloc[0]['thstrm_amount']
                            return float(str(val).replace(',', ''))
                        except: return 0
                    sales = get_val(['매출액', '수익(매출액)', '영업수익'])
                    op = get_val(['영업이익', '영업이익(손실)'])
                    net = get_val(['당기순이익', '당기순이익(손실)'])
                    if sales != 0 or op != 0:
                        result_data.append({'연도': str(year), '매출액': sales, '영업이익': op, '순이익': net})
            except: pass
            time.sleep(0.05)
        if result_data:
            df_dart = pd.DataFrame(result_data)
            df_shares = fetch_shares_history(ticker_code)
            if not df_shares.empty: df_final = pd.merge(df_dart, df_shares, on='연도', how='left')
            else: df_final = df_dart; df_final['상장주식수'] = 0
            df_final = df_final.sort_values('연도', ascending=False)
            df_final['매출액(억)'] = (df_final['매출액'] / 100000000).round(0)
            df_final['영업이익(억)'] = (df_final['영업이익'] / 100000000).round(0)
            df_final['순이익(억)'] = (df_final['순이익'] / 100000000).round(0)
            df_final['EPS(원)'] = df_final.apply(lambda r: r['순이익']/r['상장주식수'] if r.get('상장주식수',0)>0 else 0, axis=1).round(0)
            if '시가총액' in df_final.columns:
                df_final['시가총액(억)'] = (df_final['시가총액'] / 100000000).round(0)
                df_final['멀티플(배)'] = df_final.apply(lambda r: r['시가총액']/r['영업이익'] if r.get('영업이익',0)>0 else 0, axis=1).round(1)
            return df_final, "OK"
        else: return None, "No Data"
    except Exception as e: return None, str(e)

def draw_chart(ticker, period, title, unit, current_price=None, target_min=None, target_max=None, target_buy=None):
    try:
        interval = "1d" if period == "3mo" else "1wk"
        df = yf.download(ticker, period=period, interval=interval)
        if df.empty: return st.write(f"{title} 데이터 없음")
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name=title)])
        if current_price and current_price > 0:
            fig.add_hline(y=current_price, line_dash="dot", line_color="#FF4081", line_width=1)
        if target_buy and target_buy > 0:
            fig.add_hline(y=target_buy, line_width=2, line_color="#FFFFFF", opacity=1.0)
        if target_min and target_min > 0:
            fig.add_hline(y=target_min, line_dash="dot", line_color="#00C853", opacity=0.8)
        if target_max and target_max > 0:
            fig.add_hline(y=target_max, line_dash="dash", line_color="#FF3D00", opacity=0.8)
        fig.update_layout(title=dict(text=f"{title} ({unit})", font=dict(size=20)), height=450, template="plotly_white", margin=dict(l=10, r=10, b=10, t=50), xaxis_rangeslider_visible=False)
        return st.plotly_chart(fig, use_container_width=True)
    except Exception as e: return st.write(f"차트 에러: {e}")


# =========================================================
# 4. 고속 ADR 수집 및 차트 (병렬 처리 + 스타일링)
# =========================================================

# 1일치 ADR 계산 함수 (병렬 처리를 위해 분리)
def get_daily_adr(date_str, market_type):
    try:
        df_day = stock.get_market_ohlcv_by_ticker(date_str, market=market_type)
        if df_day is not None and not df_day.empty:
            up = len(df_day[df_day['등락률'] > 0])
            down = len(df_day[df_day['등락률'] < 0])
            if down > 0: return date_str, (up / down) * 100
            else: return date_str, 100.0
    except:
        return date_str, None
    return date_str, None

@st.cache_data(ttl=3600 * 12) # 12시간 캐시
def fetch_adr_history_threaded(market_type, days=365):
    """
    ThreadPoolExecutor를 사용하여 병렬로 데이터를 긁어옵니다. (속도 10배 향상)
    """
    try:
        end_date = datetime.datetime.now().strftime("%Y%m%d")
        dates = stock.get_previous_business_days(end_date=end_date, count=days)
        
        if not dates: return pd.DataFrame()

        results = {}
        market_tick = "KOSPI" if market_type == "KOSPI" else "KOSDAQ"
        
        # 진행바 설정
        progress_text = f"🚀 {market_type} {days}일치 데이터 고속 수집 중..."
        my_bar = st.progress(0, text=progress_text)
        
        # 병렬 처리 (워커 8개)
        with ThreadPoolExecutor(max_workers=8) as executor:
            # 작업 예약
            future_to_date = {executor.submit(get_daily_adr, date, market_tick): date for date in dates}
            
            completed_count = 0
            for future in as_completed(future_to_date):
                date_str, adr_val = future.result()
                if adr_val is not None:
                    results[date_str] = adr_val
                
                completed_count += 1
                if completed_count % 10 == 0:
                    my_bar.progress(completed_count / len(dates), text=f"{progress_text} ({completed_count}/{len(dates)})")
        
        my_bar.empty()
        
        # 결과 정리
        if not results: return pd.DataFrame()
        
        df = pd.DataFrame(list(results.items()), columns=['Date', 'ADR'])
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').set_index('Date')
        
        # 20일 이동평균선 (실제 ADR 차트의 핵심)
        df['ADR_MA20'] = df['ADR'].rolling(window=20).mean()
        
        # 앞부분 결측치는 원본 값으로 대체
        df['ADR_MA20'] = df['ADR_MA20'].fillna(df['ADR'])
        
        return df
        
    except Exception as e:
        st.error(f"데이터 수집 중 오류: {e}")
        return pd.DataFrame()

def draw_adr_chart_fancy(df, market_type):
    if df is None or df.empty:
        return st.warning("데이터가 없습니다.")

    # 최근 데이터
    current_adr = df['ADR_MA20'].iloc[-1]
    
    # 색상 설정 (KOSPI: 그레이/블루, KOSDAQ: 그레이/그린)
    line_color = "#5C6BC0" if market_type == "KOSPI" else "#26A69A"
    
    fig = go.Figure()

    # ADR 라인 (메인)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['ADR_MA20'],
        mode='lines',
        name='ADR',
        line=dict(color='#90A4AE', width=2), # 기본 회색
        fill='tozeroy',
        fillcolor='rgba(236, 240, 241, 0.5)' # 하단 채우기 (연하게)
    ))
    
    # 최근 20일 강조 라인 (색상)
    df_recent = df.tail(20)
    fig.add_trace(go.Scatter(
        x=df_recent.index, y=df_recent['ADR_MA20'],
        mode='lines',
        name='Current',
        line=dict(color=line_color, width=3),
        showlegend=False
    ))

    # Min / Max 포인트 찾기 (최근 1년 내)
    max_val = df['ADR_MA20'].max()
    max_date = df['ADR_MA20'].idxmax()
    min_val = df['ADR_MA20'].min()
    min_date = df['ADR_MA20'].idxmin()

    # Annotation (최고점)
    fig.add_annotation(
        x=max_date, y=max_val,
        text=f"MAX: {max_val:.1f}",
        showarrow=True, arrowhead=2, arrowcolor="#FF5252",
        font=dict(color="#FF5252", size=11, weight="bold"),
        bgcolor="rgba(255,255,255,0.8)"
    )

    # Annotation (최저점)
    fig.add_annotation(
        x=min_date, y=min_val,
        text=f"MIN: {min_val:.1f}",
        showarrow=True, arrowhead=2, arrowcolor="#2962FF",
        ax=0, ay=30, # 아래로 화살표
        font=dict(color="#2962FF", size=11, weight="bold"),
        bgcolor="rgba(255,255,255,0.8)"
    )
    
    # 현재가 마커
    fig.add_trace(go.Scatter(
        x=[df.index[-1]], y=[current_adr],
        mode='markers+text',
        marker=dict(size=10, color=line_color, line=dict(width=2, color='white')),
        text=[f"{current_adr:.1f}"],
        textposition="top center",
        textfont=dict(color=line_color, weight="bold"),
        showlegend=False
    ))

    # 기준선 (120: 과열, 80: 침체)
    fig.add_hline(y=120, line_dash="dash", line_color="#FF8A80", line_width=1, opacity=0.7)
    fig.add_annotation(x=df.index[0], y=120, text="과열 (120)", showarrow=False, yshift=10, xanchor="left", font=dict(color="#FF8A80", size=10))
    
    fig.add_hline(y=80, line_dash="dash", line_color="#80D8FF", line_width=1, opacity=0.7)
    fig.add_annotation(x=df.index[0], y=80, text="침체 (80)", showarrow=False, yshift=10, xanchor="left", font=dict(color="#80D8FF", size=10))

    # 레이아웃 설정 (화이트 테마, 기간 선택 버튼)
    fig.update_layout(
        title=dict(text=f"<b>{market_type}</b> ADR Chart", x=0.5, xanchor='center', font=dict(size=20, color='#333')),
        template="plotly_white",
        height=450,
        margin=dict(t=50, b=20, l=20, r=20),
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=2, label="2y", step="year", stepmode="backward"),
                    dict(step="all", label="All")
                ]),
                bgcolor="#f0f2f6",
                activecolor="#dfe6e9",
                font=dict(color="black")
            ),
            type="date",
            showgrid=False
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#f1f3f4",
            range=[50, 150] # ADR 범위 고정
        ),
        hovermode="x unified"
    )

    return st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


# =========================================================
# 5. 메인 앱 실행 로직
# =========================================================
df_sheet = load_data()

st.sidebar.title("사장님 투자 터미널")
menu = st.sidebar.radio("메뉴 선택", ["📊 개별 종목 분석", "🌍 시장 대시보드 (Beta)"])
st.sidebar.markdown("---")

if menu == "📊 개별 종목 분석":
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
                ticker_obj = yf.Ticker(yf_code)
                history = ticker_obj.history(period="1d")
                current_p = history['Close'].iloc[-1] if not history.empty else 0

                summary_text = "정보 가져오는 중..."
                source_label = ""
                try:
                    if is_korea:
                        naver_text = fetch_naver_summary(dart_code)
                        if naver_text:
                            raw_text = naver_text
                            source_label = "(출처: 네이버 금융)"
                        else:
                            raw_text = ticker_obj.info.get('longBusinessSummary', '')
                            source_label = ""
                    else:
                        raw_text = ticker_obj.info.get('longBusinessSummary', '')
                        source_label = ""

                    if raw_text:
                        is_english = not re.search('[가-힣]', raw_text[:20]) 
                        if is_english:
                            translated_text = GoogleTranslator(source='auto', target='ko').translate(raw_text[:3000])
                        else:
                            translated_text = raw_text
                        sentences = translated_text.split('. ')
                        formatted_text = ""
                        for i, sentence in enumerate(sentences):
                            clean_sentence = sentence.strip()
                            if not clean_sentence.endswith('.'): clean_sentence += "."
                            formatted_text += clean_sentence + " "
                            if (i + 1) % 3 == 0: formatted_text += "<br><br>"
                        summary_text = formatted_text
                    else:
                        summary_text = "제공된 정보 없음"
                except: summary_text = "불러오기 실패"

                gap_min = ((t_min - current_p)/current_p)*100 if current_p else 0
                gap_max = ((t_max - current_p)/current_p)*100 if current_p else 0
                gap_buy = ((t_buy - current_p)/current_p)*100 if current_p else 0
                cagr_min = ((t_min/current_p)**(1/7)-1)*100 if current_p and t_min else 0
                cagr_max = ((t_max/current_p)**(1/7)-1)*100 if current_p and t_max else 0
                grade = s_info.get('투자등급', '미분류') 
                badge_color = {"코어": "#2962FF", "위성": "#FFAB00", "시가존": "#2E7D32"}.get(grade, "#616161")
                badge_icon = {"코어": "💎", "위성": "🛰️", "시가존": "🚬"}.get(grade, "❔")
                badge_text = {"코어": "코어 (주력 후보)", "위성": "위성 (모멘텀 후보)", "시가존": "시가존 (분할 매수)"}.get(grade, "미지정")

                port_status = str(s_info.get('포트상태', '')).strip()
                port_badge_html = ""
                if '보유' in port_status or '편입' in port_status:
                    port_badge_html = f"""<div style="margin-top: 5px; background-color: #00C853; padding: 5px 10px; border-radius: 5px; color: white; font-weight: bold; font-size: 0.9em;">💰 포트 편입중</div>"""
                elif '정리' in port_status or '매도' in port_status:
                    port_badge_html = f"""<div style="margin-top: 5px; background-color: #616161; padding: 5px 10px; border-radius: 5px; color: white; font-weight: bold; font-size: 0.9em;">👋 포트 정리완료</div>"""

            except:
                current_p = 0; gap_min=gap_max=gap_buy=cagr_min=cagr_max=0
                summary_text = "데이터 없음"
                port_badge_html = ""

            st.title(f"🚀 {selected} ({dart_code if is_korea else yf_code}) 기업 가치")
            tab1, tab2 = st.tabs(["🚀 종목 대시보드", "💎 가치분석 (매출/영업/EPS)"])

            with tab1:
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("실시간 현재가", f"{unit}{p_format.format(current_p)}")
                    st.markdown(f"""
                        <div style="background-color: {badge_color}; padding: 5px 10px; border-radius: 5px; color: white; font-weight: bold;">{badge_icon} {badge_text}</div>
                        {port_badge_html}
                    """, unsafe_allow_html=True)

                with c2: st.metric("⚡ 매수 가치", f"{unit}{p_format.format(t_buy)}", f"{gap_buy:.1f}%")
                with c3: 
                    st.metric("🛡️ 보수적 적정가", f"{unit}{p_format.format(t_min)}", f"{gap_min:.1f}%")
                    if cagr_min: st.markdown(f"<div style='background-color:#7B1FA2;color:white;padding:8px;border-radius:5px;font-size:16px;font-weight:bold;'>📈 7~10년 CAGR {cagr_min:+.1f}%</div>", unsafe_allow_html=True)
                with c4: 
                    st.metric("🚀 최대 미래가치", f"{unit}{p_format.format(t_max)}", f"{gap_max:.1f}%")
                    if cagr_max: st.markdown(f"<div style='background-color:#7B1FA2;color:white;padding:8px;border-radius:5px;font-size:16px;font-weight:bold;'>📈 7~10년 CAGR {cagr_max:+.1f}%</div>", unsafe_allow_html=True)
                
                st.write("---")
                
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
                    with st.spinner(f"연간 데이터 분석 중... (DART)"):
                        display_df, msg = fetch_core_financials_dart(DART_API_KEY, dart_code)
                    
                    if display_df is not None:
                        raw_data = display_df.sort_values('연도')
                        eps_series = raw_data['EPS(원)']
                        eps_mean_10 = eps_series.mean()
                        eps_mean_5 = eps_series.tail(5).mean()
                        latest_eps = eps_series.iloc[-1]
                        latest_vs_10y_rate = ((latest_eps - eps_mean_10) / eps_mean_10) * 100 if eps_mean_10 > 0 else 0
                        momentum_avg = ((eps_mean_5 - eps_mean_10) / eps_mean_10) * 100 if eps_mean_10 > 0 else 0
                        df_max = raw_data
                        period_max = len(df_max)
                        label_max = f"{period_max}년 연평균(CAGR)" if period_max < 10 else "10년 연평균(CAGR)"
                        def calculate_cagr(series):
                            if len(series) < 2: return "데이터 부족"
                            start_val = series.iloc[0]
                            end_val = series.iloc[-1]
                            years = len(series) - 1
                            if start_val <= 0: start_val = 1 
                            if end_val <= 0: return "적자 지속"
                            try:
                                cagr = (end_val / start_val) ** (1/years) - 1
                                return f"{cagr*100:+.1f}%"
                            except: return "계산 오류"
                        cagr_max_str = calculate_cagr(eps_series)
                        cagr_5_str = calculate_cagr(eps_series.tail(5))
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
                        st.markdown("### 📊 연간 실적 (10년)")
                        view_cols = ['연도', '매출액(억)', '영업이익(억)', '순이익(억)', 'EPS(원)']
                        if '시가총액(억)' in display_df.columns: view_cols.append('시가총액(억)')
                        if '멀티플(배)' in display_df.columns: view_cols.append('멀티플(배)')
                        st.dataframe(display_df[view_cols].set_index('연도').T.style.format("{:,.0f}"), use_container_width=True)
                        fig = make_subplots(specs=[[{"secondary_y": True}]])
                        fig.add_trace(go.Bar(x=raw_data['연도'], y=raw_data['매출액(억)'], name='매출액(좌측)', marker_color='#90CAF9', opacity=0.6), secondary_y=False)
                        fig.add_trace(go.Bar(x=raw_data['연도'], y=raw_data['영업이익(억)'], name='영업이익(좌측)', marker_color='#2962FF'), secondary_y=False)
                        fig.add_trace(go.Scatter(x=raw_data['연도'], y=raw_data['EPS(원)'], name='EPS', mode='lines+markers+text', line=dict(color='#00E676', width=3), text=raw_data['EPS(원)'].apply(lambda x: f"{x:,.0f}"), textposition="top center"), secondary_y=True)
                        fig.add_hline(y=eps_mean_10, line_dash="dash", line_color="#FFAB00", line_width=2, secondary_y=True, annotation_text=f"10년평균: {eps_mean_10:,.0f}", annotation_position="top left", annotation_font_color="#FFAB00")
                        fig.add_hline(y=eps_mean_5, line_dash="dot", line_color="#D500F9", line_width=2, secondary_y=True, annotation_text=f"5년평균: {eps_mean_5:,.0f}", annotation_position="bottom left", annotation_font_color="#D500F9")
                        fig.update_layout(title=f"{selected} 연간 실적 추이", template="plotly_white", barmode='group', height=550, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                        fig.update_yaxes(title_text="금액 (억 원)", secondary_y=False, showgrid=True, gridcolor='#f1f3f4')
                        fig.update_yaxes(title_text="EPS (원)", secondary_y=True, showgrid=False)
                        st.plotly_chart(fig, use_container_width=True)
                    else: st.warning(f"데이터를 가져오지 못했습니다. ({msg})")

        else: st.warning("종목 없음")
    else: st.error("데이터 로딩 실패")

elif menu == "🌍 시장 대시보드 (Beta)":
    st.title("ADR Chart")
    st.markdown("<p style='color:gray; margin-top:-15px;'>코스피, 코스닥 ADR 지표 차트입니다.</p>", unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-box">
        <b>💡 ADR(등락비율)이란?</b><br>
        20일 이동평균선 기준, <b>80 이하는 과매도(침체)</b>로 매수 기회, <b>120 이상은 과매수(과열)</b>로 현금 확보 시그널로 해석합니다.<br>
        (데이터 수집에 약 15~20초 소요됩니다. 병렬 처리 적용됨)
    </div>
    """, unsafe_allow_html=True)
    
    try:
        usd_krw = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
        st.sidebar.markdown(f"### 💵 원/달러 환율: {usd_krw:,.2f}원")
    except: pass

    # 탭 이름도 영어로 (스타일 통일)
    m_tab1, m_tab2 = st.tabs(["KOSPI", "KOSDAQ"])
    
    with m_tab1:
        # 병렬 수집 함수 호출 (최대 365일)
        df_kospi = fetch_adr_history_threaded("KOSPI", days=365)
        
        if not df_kospi.empty:
            curr_adr = df_kospi['ADR_MA20'].iloc[-1]
            st.metric("현재 KOSPI ADR", f"{curr_adr:.1f}%", delta=f"{curr_adr-100:.1f}")
            draw_adr_chart_fancy(df_kospi, "KOSPI")
        else:
            st.warning("데이터 수집에 실패했습니다. (네이버 금융 응답 지연)")

    with m_tab2:
        df_kosdaq = fetch_adr_history_threaded("KOSDAQ", days=365)
        
        if not df_kosdaq.empty:
            curr_adr = df_kosdaq['ADR_MA20'].iloc[-1]
            st.metric("현재 KOSDAQ ADR", f"{curr_adr:.1f}%", delta=f"{curr_adr-100:.1f}")
            draw_adr_chart_fancy(df_kosdaq, "KOSDAQ")
        else:
            st.warning("데이터 수집에 실패했습니다. (네이버 금융 응답 지연)")
