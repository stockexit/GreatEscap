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
    /* 탭 스타일 */
    button[data-baseweb="tab"] div p { font-size: 18px !important; font-weight: bold !important; }
    
    /* 테이블 헤더 */
    thead tr th { background-color: #f5f6f7 !important; color: #333 !important; font-weight: bold !important; }
    
    /* 메트릭 스타일 */
    div[data-testid="stMetricValue"] { font-size: 26px !important; }
    div[data-testid="stMetricDelta"] {
        font-size: 18px !important;
        font-weight: bold !important;
        background-color: rgba(0, 200, 83, 0.2) !important;
        padding: 5px 10px !important;
        border-radius: 10px !important;
    }
    
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
# 3. 개별 종목 분석용 함수들 (기존 기능 유지)
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
# 4. 시장 대시보드 함수 (에러 수정 및 기능 강화)
# =========================================================
@st.cache_data(ttl=3600 * 6) # 6시간 캐싱
def fetch_market_data_with_adr(market_type, days=365): 
    """
    market_type: 'KOSPI' or 'KOSDAQ'
    days: 조회 기간 (기본 1년)
    """
    try:
        # 1. 지수 데이터 (Yfinance 이용 - 훨씬 빠르고 안정적)
        ticker = "^KS11" if market_type == "KOSPI" else "^KQ11"
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=days + 20) # 이평선 계산 위해 여유 기간
        
        df_index = yf.download(ticker, start=start_date, end=end_date, progress=False)
        
        if df_index.empty:
            return pd.DataFrame()
            
        # 컬럼 정리 (MultiIndex 문제 해결)
        if isinstance(df_index.columns, pd.MultiIndex):
            # 'Close' 컬럼이 있으면 가져오고, 없으면 첫번째 컬럼 사용
            try:
                df_index = df_index.xs('Close', level=0, axis=1)
            except:
                pass
            
            if isinstance(df_index.columns, pd.MultiIndex): # 여전히 멀티인덱스면
                 df_index.columns = df_index.columns.get_level_values(0)

        # 종가 컬럼 찾기
        close_col = 'Close' if 'Close' in df_index.columns else df_index.columns[0]
        df_index = df_index[[close_col]].rename(columns={close_col: 'Index'})
        df_index.index = pd.to_datetime(df_index.index).strftime('%Y%m%d') # 인덱스 포맷 통일
        
        # 2. ADR 데이터 (Pykrx 이용 - 루프 필요)
        # 타임아웃 방지를 위해 최근 데이터부터 역순으로 가져오다가 실패하면 멈춤
        market_code = "1001" if market_type == "KOSPI" else "2001" # 1001: KOSPI, 2001: KOSDAQ
        
        # 영업일 가져오기
        end_str = end_date.strftime("%Y%m%d")
        dates = stock.get_previous_business_days(end_date=end_str, count=days)
        
        if not dates:
            # 날짜 못 가져오면 지수만 리턴
            return df_index
            
        adr_data = []
        
        # 진행률 표시
        progress_text = f"📊 {market_type} 데이터 수집 중... (서버 상황에 따라 시간이 소요됩니다)"
        my_bar = st.progress(0, text=progress_text)
        
        for i, date_str in enumerate(dates):
            try:
                # 너무 빠르면 차단되므로 0.1초 지연
                time.sleep(0.05)
                
                # 해당 일자 등락 종목 수 가져오기
                df_day = stock.get_market_ohlcv_by_ticker(date_str, market=market_type)
                
                if df_day is not None and not df_day.empty:
                    up = len(df_day[df_day['등락률'] > 0])
                    down = len(df_day[df_day['등락률'] < 0])
                    
                    if down > 0: adr = (up / down) * 100
                    else: adr = 100.0
                    
                    adr_data.append({'Date': date_str, 'ADR': adr})
            except Exception:
                # 하루 실패해도 건너뛰고 계속 진행 (전체 실패 방지)
                pass
                
            # 진행바 업데이트 (5일마다)
            if i % 5 == 0:
                my_bar.progress((i + 1) / len(dates), text=f"{progress_text} ({i}/{len(dates)}일 완료)")

        my_bar.empty()
        
        # ADR 데이터프레임 생성
        if adr_data:
            df_adr = pd.DataFrame(adr_data)
            df_adr['Date'] = pd.to_datetime(df_adr['Date']).dt.strftime('%Y%m%d') # 키 통일
            df_adr = df_adr.set_index('Date')
            
            # 3. 지수와 ADR 병합
            df_final = df_index.join(df_adr, how='inner') # 교집합만
            
            # ADR 20일 이평선 (차트를 부드럽게)
            df_final['ADR_MA20'] = df_final['ADR'].rolling(window=20).mean()
            
            # 이평선이 없는 앞부분 데이터는 원본 ADR 값으로 채움
            df_final['ADR_MA20'] = df_final['ADR_MA20'].fillna(df_final['ADR'])
            
            return df_final.dropna()
        else:
            # ADR 실패 시 지수만 리턴
            df_index['ADR'] = None
            return df_index

    except Exception as e:
        st.error(f"데이터 수집 에러 상세: {e}")
        return pd.DataFrame()

def draw_market_chart(df, market_type):
    if df is None or df.empty:
        return st.warning("데이터를 불러오지 못했습니다. (네이버 금융 접속 제한 등)")
    
    # 색상 테마 설정
    if market_type == "KOSPI":
        color_index = "#2962FF" # 파랑
        color_adr = "#FF1744"   # 빨강
        title = "ADR - KOSPI"
    else:
        color_index = "#00C853" # 초록
        color_adr = "#FF9100"   # 주황
        title = "ADR - KOSDAQ"

    # 차트 그리기
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 1. 지수 (왼쪽 축)
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df['Index'], 
            name=f"{market_type} 지수", 
            line=dict(color=color_index, width=2)
        ), 
        secondary_y=False
    )
    
    # 2. ADR (오른쪽 축) - 데이터가 있을 때만
    if 'ADR' in df.columns and df['ADR'].notnull().any():
        # 이평선 우선, 없으면 원본
        y_data = df['ADR_MA20'] if 'ADR_MA20' in df.columns and df['ADR_MA20'].notnull().any() else df['ADR']
        
        fig.add_trace(
            go.Scatter(
                x=df.index, y=y_data, 
                name="ADR (시장심리)", 
                line=dict(color=color_adr, width=2)
            ), 
            secondary_y=True
        )

        # 기준선 (오른쪽 축 기준)
        fig.add_hline(y=100, line_dash="solid", line_color="gray", line_width=1, opacity=0.3, secondary_y=True)
        fig.add_hline(y=75, line_dash="dot", line_color="#00E676", opacity=0.8, annotation_text="침체 (75)", annotation_position="bottom right", secondary_y=True)
        fig.add_hline(y=125, line_dash="dot", line_color="#FF5252", opacity=0.8, annotation_text="과열 (125)", annotation_position="top right", secondary_y=True)

    # 레이아웃 설정
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color="#E0E0E0")),
        height=500, 
        template="plotly_dark", 
        hovermode="x unified", 
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=60, b=20),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    
    # Y축 설정
    fig.update_yaxes(title_text="", showgrid=False, secondary_y=False, tickfont=dict(color=color_index))
    fig.update_yaxes(
        title_text="", 
        showgrid=True, gridcolor='rgba(255,255,255,0.1)', 
        range=[60, 140], # ADR 범위 고정
        secondary_y=True,
        tickfont=dict(color=color_adr)
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
                        fig.update_layout(title=f"{selected} 연간 실적 추이", template="plotly_dark", barmode='group', height=550, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                        fig.update_yaxes(title_text="금액 (억 원)", secondary_y=False, showgrid=True, gridcolor='rgba(255,255,255,0.1)')
                        fig.update_yaxes(title_text="EPS (원)", secondary_y=True, showgrid=False)
                        st.plotly_chart(fig, use_container_width=True)
                    else: st.warning(f"데이터를 가져오지 못했습니다. ({msg})")

        else: st.warning("종목 없음")
    else: st.error("데이터 로딩 실패")

elif menu == "🌍 시장 대시보드 (Beta)":
    st.title("🌍 KOREA Market Dashboard")
    st.markdown("""
    <div style="background-color:rgba(41, 98, 255, 0.1); padding:10px; border-radius:5px; border: 1px solid #2962FF; margin-bottom: 20px;">
        💡 <b>지수(왼쪽)</b>와 <b>ADR(오른쪽)</b>을 함께 봅니다. <br>
        • ADR 80 이하: <b>과매도(침체)</b> → 매수 기회 <br>
        • ADR 120 이상: <b>과매수(과열)</b> → 현금 확보 필요
    </div>
    """, unsafe_allow_html=True)
    
    try:
        usd_krw = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
        st.sidebar.markdown(f"### 💵 원/달러 환율: {usd_krw:,.2f}원")
    except: pass

    m_tab1, m_tab2 = st.tabs(["KOSPI (코스피)", "KOSDAQ (코스닥)"])
    
    with m_tab1:
        df_kospi = fetch_market_data_with_adr("KOSPI", days=365)
        
        if not df_kospi.empty:
            if 'ADR' in df_kospi.columns and df_kospi['ADR'].notnull().any():
                curr_adr = df_kospi['ADR'].iloc[-1]
                st.metric("현재 KOSPI ADR", f"{curr_adr:.1f}%", delta=f"{curr_adr-100:.1f}")
            draw_market_chart(df_kospi, "KOSPI")
        else:
            st.warning("데이터 수집에 실패했습니다. (잠시 후 다시 시도)")

    with m_tab2:
        df_kosdaq = fetch_market_data_with_adr("KOSDAQ", days=365)
        
        if not df_kosdaq.empty:
            if 'ADR' in df_kosdaq.columns and df_kosdaq['ADR'].notnull().any():
                curr_adr = df_kosdaq['ADR'].iloc[-1]
                st.metric("현재 KOSDAQ ADR", f"{curr_adr:.1f}%", delta=f"{curr_adr-100:.1f}")
            draw_market_chart(df_kosdaq, "KOSDAQ")
        else:
            st.warning("데이터 수집에 실패했습니다. (잠시 후 다시 시도)")
