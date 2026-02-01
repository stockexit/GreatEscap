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
    page_title="사장님 투자 터미널 (Pro)", 
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

    /* 버튼 스타일링 */
    div[role="radiogroup"] {
        background-color: transparent;
        padding: 5px 0;
        margin-bottom: 10px;
    }
    div[role="radiogroup"] label {
        background-color: #1e1e1e;
        border: 1px solid #444;
        padding: 5px 20px;
        border-radius: 6px;
        font-weight: bold;
        margin-right: 8px;
    }
    div[role="radiogroup"] label[data-checked="true"] {
        background-color: #FF4B4B !important;
        color: white !important;
        border-color: #FF4B4B !important;
    }
</style>
""", unsafe_allow_html=True)

ssl._create_default_https_context = ssl._create_unverified_context

# =========================================================
# 2. 데이터 로딩
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
# 3. 데이터 수집 함수들 (FnGuide 크롤링 적용)
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

# [핵심] FnGuide 연간/분기 데이터 크롤링 (가장 정확함)
@st.cache_data(show_spinner=False)
def fetch_fnguide_financials(ticker_code):
    """FnGuide에서 재무제표 크롤링 (정확도 최우선)"""
    try:
        # FnGuide 재무제표 페이지 (IFRS 연결 기준)
        url = f"https://comp.fnguide.com/SVO2/ASP/SVD_Finance.asp?pGB=1&gicode=A{ticker_code}&cID=&MenuYn=Y&ReportGB=D&NewMenuID=103&stkGb=701"
        
        # 테이블 읽기
        dfs = pd.read_html(requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text)
        
        # dfs[0]: 연간 포괄손익계산서, dfs[1]: 분기 포괄손익계산서
        df_annual = dfs[0]
        df_quarter = dfs[1]
        
        # 데이터 정리 함수
        def clean_fnguide_df(df, type_name):
            # 첫 번째 컬럼(계정명)을 인덱스로
            df = df.set_index(df.columns[0])
            
            # 필요한 행만 추출 (매출액, 영업이익, 당기순이익)
            # FnGuide 계정명: '매출액', '영업이익', '당기순이익' (지배주주 순이익이 더 정확할 수 있으나 일단 전체 순이익)
            target_rows = {
                '매출액': '매출액(억)',
                '영업이익': '영업이익(억)',
                '당기순이익': '순이익(억)' 
            }
            
            result_list = []
            
            # 컬럼(기간) 순회
            for col in df.columns:
                # '전년동기' 같은 비교 컬럼 제외하고 날짜형식(YYYY/MM)만 가져오기
                if not re.search(r'\d{4}/\d{2}', col): continue
                
                # 기간 이름 정리 (2024/12 -> 2024.4Q or 2024)
                period_str = col
                if type_name == 'quarter':
                    # 분기 포맷 변환 (2024/03 -> 2024.1Q)
                    try:
                        y, m = col.split('/')
                        q = (int(m) - 1) // 3 + 1
                        period_clean = f"{y}.{q}Q"
                    except: period_clean = col
                else:
                    # 연간 포맷
                    period_clean = col.split('/')[0]

                data = {'기간': period_clean}
                
                for key, new_key in target_rows.items():
                    try:
                        # 해당 계정명이 포함된 행 찾기
                        val = df.loc[df.index.str.contains(key), col].iloc[0]
                        if pd.notna(val):
                            data[new_key] = int(val) # FnGuide는 이미 억 단위
                        else:
                            data[new_key] = 0
                    except: 
                        data[new_key] = 0
                
                result_list.append(data)
                
            return pd.DataFrame(result_list)

        df_a_clean = clean_fnguide_df(df_annual, 'annual')
        df_q_clean = clean_fnguide_df(df_quarter, 'quarter')
        
        # 연간 데이터는 최신순 정렬
        df_a_clean = df_a_clean.sort_values('기간', ascending=False)
        # 분기 데이터는 최신순 정렬
        df_q_clean = df_q_clean.sort_values('기간', ascending=False)
        
        return df_a_clean, df_q_clean

    except Exception as e:
        return None, None

# [EPS 및 주가 정보 보강용] - 기존 DART 로직 일부 활용 (EPS 계산 등 보조)
# 하지만 표시는 FnGuide 데이터로 대체함.
@st.cache_data(show_spinner=False)
def get_eps_growth_info(api_key, ticker_code, fnguide_annual):
    # EPS 성장률 등 지표 계산은 정확한 FnGuide 연간 데이터를 기반으로 함
    try:
        # 시가총액 정보 가져오기
        df_shares = fetch_shares_history(ticker_code)
        
        # FnGuide 데이터와 병합
        if fnguide_annual is not None and not fnguide_annual.empty and not df_shares.empty:
            merged = pd.merge(fnguide_annual, df_shares, left_on='기간', right_on='연도', how='left')
            merged['EPS(원)'] = merged.apply(lambda x: x['순이익(억)'] * 100000000 / x['상장주식수'] if x['상장주식수'] > 0 else 0, axis=1)
            return merged
        return fnguide_annual
    except:
        return fnguide_annual

# =========================================================
# 5. 차트 함수 & 시장 지표 함수
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

@st.cache_data(ttl=3600 * 4) 
def fetch_market_data_with_adr(market_code, days=60):
    try:
        now = datetime.datetime.now()
        end_date = now.strftime("%Y%m%d")
        start_date_idx = (now - datetime.timedelta(days=days+20)).strftime("%Y%m%d")

        df_index = stock.get_index_ohlcv_by_date(start_date_idx, end_date, market_code)
        if df_index.empty: return pd.DataFrame()
        df_index = df_index[['종가']].rename(columns={'종가': 'Index'})

        market_tick = "KOSPI" if market_code == "1001" else "KOSDAQ"
        dates = stock.get_previous_business_days(end_date=end_date, count=days)
        
        adr_results = []
        progress_bar = st.progress(0)
        
        if not dates: 
             progress_bar.empty()
             return pd.DataFrame()

        for i, date_str in enumerate(dates):
            try:
                df_day = stock.get_market_ohlcv_by_ticker(date_str, market=market_tick)
                if df_day is not None and not df_day.empty:
                    up_count = len(df_day[df_day['등락률'] > 0])
                    down_count = len(df_day[df_day['등락률'] < 0])
                    if down_count > 0: adr = (up_count / down_count) * 100
                    else: adr = 100
                    adr_results.append({"Date": pd.to_datetime(date_str), "ADR": adr})
            except: pass 
            progress_bar.progress((i + 1) / len(dates))
            time.sleep(0.05) 
            
        progress_bar.empty()
        
        if not adr_results: return pd.DataFrame()
        df_adr = pd.DataFrame(adr_results)
        if 'Date' not in df_adr.columns: return pd.DataFrame()
        df_adr = df_adr.set_index('Date').sort_index()
        
        df_final = pd.merge(df_index, df_adr, left_index=True, right_index=True, how='inner')
        return df_final
    except Exception as e:
        return pd.DataFrame()

def draw_market_chart(df, title):
    if df.empty: return st.warning("데이터를 불러오지 못했습니다.")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=df.index, y=df['Index'], name=title.split(' ')[0], line=dict(color='#2962FF', width=2)), secondary_y=False)
    fig.add_trace(go.Scatter(x=df.index, y=df['ADR'], name='ADR(등락비율)', line=dict(color='#FF3D00', width=2)), secondary_y=True)
    fig.add_hline(y=100, line_dash="dash", line_color="gray", opacity=0.5, secondary_y=True)
    fig.add_hline(y=80, line_dash="dot", line_color="#00C853", opacity=0.7, annotation_text="침체 (80)", annotation_position="bottom right", secondary_y=True)
    fig.add_hline(y=120, line_dash="dot", line_color="#D500F9", opacity=0.7, annotation_text="과열 (120)", annotation_position="top right", secondary_y=True)
    fig.update_layout(title=dict(text=title, font=dict(size=20)), height=500, template="plotly_dark", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), yaxis=dict(title=f"{title.split(' ')[0]} 지수", showgrid=False), yaxis2=dict(title="ADR (%)", showgrid=True, gridcolor='rgba(255,255,255,0.1)', range=[60, 140]))
    return st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# =========================================================
# 6. 메인 앱 로직
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
                            source_label = ""
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
                    with st.spinner(f"데이터 정밀 분석 중... (FnGuide)"):
                        # [핵심] FnGuide에서 연간, 분기 데이터 모두 가져옴
                        df_a, df_q = fetch_fnguide_financials(dart_code)
                        
                        # 지표 계산용 데이터 준비 (연간 데이터 + 주식수)
                        # 주식수는 fetch_shares_history로 가져와서 병합
                        df_metrics = get_eps_growth_info(DART_API_KEY, dart_code, df_a)
                    
                    if df_metrics is not None and not df_metrics.empty:
                        # EPS 데이터가 있는지 확인
                        if 'EPS(원)' in df_metrics.columns:
                            eps_series = df_metrics.sort_values('기간')['EPS(원)'].dropna()
                            if not eps_series.empty:
                                eps_mean_10 = eps_series.mean()
                                eps_mean_5 = eps_series.tail(5).mean()
                                latest_eps = eps_series.iloc[-1]
                                
                                latest_vs_10y_rate = ((latest_eps - eps_mean_10) / eps_mean_10) * 100 if eps_mean_10 > 0 else 0
                                momentum_avg = ((eps_mean_5 - eps_mean_10) / eps_mean_10) * 100 if eps_mean_10 > 0 else 0
                                
                                # CAGR 계산
                                def calculate_cagr(series):
                                    if len(series) < 2: return "데이터 부족"
                                    start_val = series.iloc[0]
                                    end_val = series.iloc[-1]
                                    years = len(series) - 1
                                    
                                    if start_val <= 0: start_val = 1 # 적자 보정
                                    if end_val <= 0: return "적자 지속"
                                    
                                    try:
                                        cagr = (end_val / start_val) ** (1/years) - 1
                                        return f"{cagr*100:+.1f}%"
                                    except: return "계산 오류"

                                cagr_max_str = calculate_cagr(eps_series)
                                cagr_5_str = calculate_cagr(eps_series.tail(5))

                                # [지표 영역]
                                c_t1, c_t2, c_t3 = st.columns(3)
                                with c_t1: st.metric("10년 평균 EPS", f"{eps_mean_10:,.0f}원")
                                with c_t2: st.metric("5년 평균 EPS", f"{eps_mean_5:,.0f}원")
                                with c_t3: st.metric("최신 EPS 성장률", "", delta=f"{latest_vs_10y_rate:+.1f}%")
                                st.write("") 
                                c_b1, c_b2, c_b3 = st.columns(3)
                                with c_b1: st.metric("10년 연평균(CAGR)", cagr_max_str)
                                with c_b2: st.metric("최근 5년 연평균", cagr_5_str)
                                with c_b3: st.metric("성장 모멘텀", "", delta=f"{momentum_avg:+.1f}%")
                                
                                st.write("---")

                        # [핵심] 보기 선택 버튼 (토글)
                        view_option = st.radio("조회 기준", ["연환산 (TTM)", "연간 실적", "분기 실적"], horizontal=True, label_visibility="collapsed")
                        st.write("")

                        if "연환산" in view_option:
                            if df_q is not None and len(df_q) >= 4:
                                df_q_sorted = df_q.sort_values('기간') # 과거->미래
                                cols_to_sum = ['매출액(억)', '영업이익(억)', '순이익(억)']
                                df_ttm = df_q_sorted.copy()
                                # 4분기 이동 합계
                                df_ttm[cols_to_sum] = df_ttm[cols_to_sum].rolling(window=4).sum()
                                df_ttm = df_ttm.dropna().sort_values('기간', ascending=False)
                                
                                st.dataframe(df_ttm.set_index('기간').T.style.format("{:,.0f}"), use_container_width=True)
                                
                                fig_ttm = go.Figure()
                                fig_ttm.add_trace(go.Bar(x=df_ttm['기간'], y=df_ttm['매출액(억)'], name='매출(TTM)', marker_color='#FFA726'))
                                fig_ttm.add_trace(go.Bar(x=df_ttm['기간'], y=df_ttm['영업이익(억)'], name='영업이익(TTM)', marker_color='#FF7043'))
                                fig_ttm.update_layout(title="연환산(TTM) 실적 추이", template="plotly_dark", barmode='group', height=400)
                                st.plotly_chart(fig_ttm, use_container_width=True)
                            else:
                                st.warning("TTM 계산을 위한 데이터가 부족합니다.")

                        elif "연간" in view_option:
                            if df_a is not None:
                                st.dataframe(df_a.set_index('기간').T.style.format("{:,.0f}"), use_container_width=True)
                                
                                fig = make_subplots(specs=[[{"secondary_y": True}]])
                                # 최신순 -> 과거순이므로 차트 그릴 땐 뒤집어야 함
                                df_a_rev = df_a.iloc[::-1]
                                
                                fig.add_trace(go.Bar(x=df_a_rev['기간'], y=df_a_rev['매출액(억)'], name='매출액', marker_color='#90CAF9', opacity=0.6), secondary_y=False)
                                fig.add_trace(go.Bar(x=df_a_rev['기간'], y=df_a_rev['영업이익(억)'], name='영업이익', marker_color='#2962FF'), secondary_y=False)
                                
                                # EPS 데이터가 있으면 추가
                                if 'EPS(원)' in df_metrics.columns:
                                    # df_metrics도 기간 기준으로 정렬
                                    eps_plot = df_metrics.sort_values('기간')
                                    fig.add_trace(go.Scatter(x=eps_plot['기간'], y=eps_plot['EPS(원)'], name='EPS', mode='lines+markers+text', line=dict(color='#00E676', width=3), text=eps_plot['EPS(원)'].apply(lambda x: f"{x:,.0f}"), textposition="top center"), secondary_y=True)

                                fig.update_layout(title=f"{selected} 연간 실적 추이", template="plotly_dark", barmode='group', height=500, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                                fig.update_yaxes(title_text="금액 (억 원)", secondary_y=False, showgrid=True, gridcolor='rgba(255,255,255,0.1)')
                                fig.update_yaxes(title_text="EPS (원)", secondary_y=True, showgrid=False)
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.warning("연간 데이터를 불러올 수 없습니다.")
                        
                        else: # 분기 선택 시
                            if df_q is not None:
                                st.dataframe(df_q.set_index('기간').T.style.format("{:,.0f}"), use_container_width=True)
                                
                                fig_q = go.Figure()
                                df_q_rev = df_q.iloc[::-1] # 차트용 정렬
                                fig_q.add_trace(go.Bar(x=df_q_rev['기간'], y=df_q_rev['매출액(억)'], name='매출액', marker_color='#90CAF9'))
                                fig_q.add_trace(go.Bar(x=df_q_rev['기간'], y=df_q_rev['영업이익(억)'], name='영업이익', marker_color='#2962FF'))
                                fig_q.update_layout(title="분기 실적 추이", template="plotly_dark", barmode='group', height=400)
                                st.plotly_chart(fig_q, use_container_width=True)
                            else:
                                st.warning("분기 데이터를 불러올 수 없습니다.")

                    else: st.warning(f"데이터를 가져오지 못했습니다. ({msg})")

        else: st.warning("종목 없음")
    else: st.error("데이터 로딩 실패")

elif menu == "🌍 시장 대시보드 (Beta)":
    st.title("🌍 KOREA Market Dashboard")
    st.info("💡 지수(파란색, 왼쪽축)와 ADR(빨간색, 오른쪽축)을 함께 보며 시장의 과열/침체를 판단합니다.")
    
    try:
        usd_krw = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
        st.sidebar.markdown(f"### 💵 원/달러 환율: {usd_krw:,.2f}원")
    except: pass

    m_tab1, m_tab2 = st.tabs(["KOSPI (코스피)", "KOSDAQ (코스닥)"])
    
    with m_tab1:
        with st.spinner("KOSPI 시장 데이터 분석 중... (최근 60일)"):
            df_kospi_combo = fetch_market_data_with_adr("1001", days=60)
            
        if not df_kospi_combo.empty:
            curr_adr = df_kospi_combo['ADR'].iloc[-1]
            st.metric("현재 KOSPI ADR", f"{curr_adr:.1f}%", delta=f"{curr_adr-100:.1f}", help="100% 기준, 80% 이하 침체, 120% 이상 과열")
            draw_market_chart(df_kospi_combo, "ADR - KOSPI")
        else:
            st.warning("현재 시장 데이터를 가져오는데 일시적인 문제가 있습니다. (pykrx 서버 응답 지연 등)")

    with m_tab2:
        with st.spinner("KOSDAQ 시장 데이터 분석 중... (최근 60일)"):
            df_kosdaq_combo = fetch_market_data_with_adr("2001", days=60)
            
        if not df_kosdaq_combo.empty:
            curr_adr = df_kosdaq_combo['ADR'].iloc[-1]
            st.metric("현재 KOSDAQ ADR", f"{curr_adr:.1f}%", delta=f"{curr_adr-100:.1f}", help="100% 기준, 80% 이하 침체, 120% 이상 과열")
            draw_market_chart(df_kosdaq_combo, "ADR - KOSDAQ")
        else:
            st.warning("현재 시장 데이터를 가져오는데 일시적인 문제가 있습니다. (pykrx 서버 응답 지연 등)")
