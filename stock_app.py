import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl
import OpenDartReader
import time
import datetime

# 1. 화면 설정
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# ---------------------------------------------------------
# [스타일] 표 디자인 (헤더 색상, 폰트 등)
# ---------------------------------------------------------
st.markdown("""
<style>
    button[data-baseweb="tab"] div p { font-size: 18px !important; font-weight: bold !important; }
    thead tr th { background-color: #f0f2f6 !important; color: #31333F !important; font-size: 15px !important; font-weight: bold !important; border-bottom: 2px solid #ccc !important;}
    tbody tr td { font-size: 14px !important; }
</style>
""", unsafe_allow_html=True)
# ---------------------------------------------------------

# 2. SSL 에러 방지
ssl._create_default_https_context = ssl._create_unverified_context

# 3. 기본 데이터 로딩
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

# ---------------------------------------------------------
# [핵심 기능] 재무제표 순서 정렬기 (Sorting Helper)
# ---------------------------------------------------------
def sort_financial_accounts(df, report_type):
    """
    뒤죽박죽 섞인 계정명을 표준 순서대로 정렬해주는 함수
    """
    # 1. 우리가 원하는 순서 (우선순위 목록)
    if '손익' in report_type or '포괄' in report_type:
        order_list = [
            '매출액', '수익(매출액)', '영업수익', '매출',
            '매출원가', '영업비용',
            '매출총이익',
            '판매비와관리비', '판매비및관리비', '판관비',
            '영업이익', '영업이익(손실)',
            '금융수익', '금융원가', '금융비용',
            '기타수익', '기타비용', '기타영업외수익', '기타영업외비용',
            '지분법이익', '관계기업투자이익',
            '법인세비용차감전계속사업이익', '법인세차감전순이익',
            '법인세비용',
            '중단영업이익',
            '당기순이익', '당기순이익(손실)',
            '지배기업소유주지분', '지배주주지분순이익',
            '비지배지분', '비지배주주지분순이익',
            '총포괄손익', '총포괄이익'
        ]
    elif '상태' in report_type: # 재무상태표
        order_list = [
            '자산총계', '유동자산', '현금및현금성자산', '재고자산', '비유동자산', '유형자산', '무형자산',
            '부채총계', '유동부채', '단기차입금', '비유동부채', '사채', '장기차입금',
            '자본총계', '지배기업소유주지분', '자본금', '이익잉여금'
        ]
    elif '현금' in report_type: # 현금흐름표
        order_list = [
            '영업활동현금흐름', '영업활동으로인한현금흐름',
            '투자활동현금흐름', '투자활동으로인한현금흐름',
            '재무활동현금흐름', '재무활동으로인한현금흐름',
            '기초현금및현금성자산', '기말현금및현금성자산'
        ]
    else:
        return df # 모르는 표는 그냥 둠

    # 2. 정렬 로직 적용
    # 데이터프레임의 인덱스(계정명)를 리스트 순서대로 다시 맞춤
    # 리스트에 없는 항목은 맨 뒤로 보냄
    
    # 현재 데이터에 있는 계정명들
    current_index = df.index.tolist()
    
    # 순서 리스트에 있는 것 먼저 담기
    sorted_index = []
    for item in order_list:
        if item in current_index:
            sorted_index.append(item)
            
    # 순서 리스트에 없는 나머지(기타 항목들) 담기
    for item in current_index:
        if item not in sorted_index:
            sorted_index.append(item)
            
    # 재정렬 실행
    return df.reindex(sorted_index)


# 4. DART 데이터 수집 함수
@st.cache_data(show_spinner=False) 
def fetch_all_financials(api_key, ticker_code):
    try:
        dart = OpenDartReader(api_key)
    except Exception as e:
         return None, f"API 키 오류: {e}"

    if len(str(ticker_code)) != 6:
        return None, "DART 조회 불가"

    now_year = datetime.datetime.now().year 
    # 최근 5년치 (필요하면 숫자 수정)
    years = range(now_year - 5, now_year + 1) 
    
    all_data_list = []
    status_text = st.empty()
    
    try:
        for year in years:
            status_text.text(f"📅 {year}년도 데이터 원본 가져오는 중...")
            try:
                df = dart.finstate(ticker_code, year, reprt_code='11011')
            except:
                df = None

            if df is not None:
                df['Year'] = str(year)
                # 필요한 컬럼만
                cols = ['Year', 'fs_div', 'sj_nm', 'account_nm', 'thstrm_amount']
                valid_cols = [c for c in cols if c in df.columns]
                all_data_list.append(df[valid_cols])
            
            time.sleep(0.1)

        status_text.empty()

        if all_data_list:
            df_final = pd.concat(all_data_list)
            
            # 숫자 변환
            def clean_number(x):
                try:
                    return float(str(x).replace(',', ''))
                except:
                    return 0
            
            df_final['thstrm_amount'] = df_final['thstrm_amount'].apply(clean_number)
            
            return df_final, "OK"
        else:
            return None, "데이터 없음"

    except Exception as e:
        status_text.empty()
        return None, f"에러: {e}"

# 5. 차트 함수
def draw_chart(ticker, period, title, unit, target_min=None, target_max=None, target_buy=None, current_price=None):
    try:
        interval = "1d" if period == "3mo" else "1wk"
        df = yf.download(ticker, period=period, interval=interval)
        if df.empty: return st.write(f"{title} 데이터 없음")
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name=title)])
        
        if current_price and current_price > 0:
            fig.add_hline(y=current_price, line_dash="dot", line_color="#FF4081", line_width=1)
            fig.add_annotation(xref="paper", x=0.5, y=current_price, text=f"<b>현재가 {unit}{current_price:,.0f}</b>", showarrow=False, xanchor="center", yshift=10, font=dict(color="white", size=16), bgcolor="#FF4081", bordercolor="white", borderwidth=1, opacity=0.9)

        if target_buy and target_buy > 0:
            fig.add_hline(y=target_buy, line_width=2, line_color="#FFFFFF", opacity=1.0)
            fig.add_annotation(xref="paper", x=0.5, y=target_buy, text=f"<b>⚡ 매수 {unit}{target_buy:,.0f}</b>", showarrow=False, yshift=0, xanchor="center", font=dict(color="black", size=16), bgcolor="#FFFFFF", bordercolor="gray", borderwidth=1, opacity=0.9)

        if target_min and target_min > 0:
            fig.add_hline(y=target_min, line_dash="dot", line_color="#00C853", opacity=0.8)
            fig.add_annotation(xref="paper", x=0.5, y=target_min, text=f"<b>🛡️ 보수 {unit}{target_min:,.0f}</b>", showarrow=False, yshift=-25, xanchor="center", font=dict(color="white", size=16), bgcolor="#00C853", bordercolor="white", borderwidth=1, opacity=0.9)

        if target_max and target_max > 0:
            fig.add_hline(y=target_max, line_dash="dash", line_color="#FF3D00", opacity=0.8)
            fig.add_annotation(xref="paper", x=0.5, y=target_max, text=f"<b>🚀 최대 {unit}{target_max:,.0f}</b>", showarrow=False, yshift=25, xanchor="center", font=dict(color="white", size=16), bgcolor="#FF3D00", bordercolor="white", borderwidth=1, opacity=0.9)
        
        fig.update_layout(title=dict(text=f"{title} ({unit})", font=dict(size=20)), height=450, template="plotly_dark", margin=dict(l=10, r=10, b=10, t=50), xaxis_rangeslider_visible=False, xaxis=dict(fixedrange=True), yaxis=dict(fixedrange=True))
        return st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})
    except Exception as e: return st.write(f"차트 에러: {e}")

# 6. 메인 로직
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
            import re
            dart_code = "".join(re.findall(r'\d+', raw_code))
            if len(dart_code) < 6: dart_code = dart_code.zfill(6)
            yf_code = dart_code + ".KQ" if raw_code.endswith(".KQ") else dart_code + ".KS"
        else:
            dart_code = raw_code
            yf_code = raw_code

        is_korea = market_choice == "한국(KRW)"
        unit = "₩" if is_korea else "$"
        p_format = "{:,.0f}" if is_korea else "{:,.2f}"
        
        # 지표 및 등급
        t_min = float(s_info.get('보수적적정가', 0))
        t_max = float(s_info.get('최대미래가치', 0))
        t_buy = float(s_info.get('매수가치', 0))
        
        try:
            ticker_obj = yf.Ticker(yf_code)
            history = ticker_obj.history(period="1d")
            current_p = history['Close'].iloc[-1] if not history.empty else 0
            
            gap_min = ((t_min - current_p)/current_p)*100 if current_p else 0
            gap_max = ((t_max - current_p)/current_p)*100 if current_p else 0
            gap_buy = ((t_buy - current_p)/current_p)*100 if current_p else 0
            cagr_min = ((t_min/current_p)**(1/7)-1)*100 if current_p and t_min else 0
            cagr_max = ((t_max/current_p)**(1/7)-1)*100 if current_p and t_max else 0
            
            grade = s_info.get('투자등급', '미분류') 
            badge_color = {"코어": "#2962FF", "위성": "#FFAB00", "시가존": "#2E7D32"}.get(grade, "#616161")
            badge_icon = {"코어": "💎", "위성": "🛰️", "시가존": "🚬"}.get(grade, "❔")
            badge_text = {"코어": "CORE", "위성": "SATELLITE", "시가존": "시가존"}.get(grade, "미지정")
            
        except:
            current_p = 0; gap_min=gap_max=gap_buy=cagr_min=cagr_max=0

        st.title(f"🚀 {selected} ({dart_code if is_korea else yf_code}) 기업 가치")

        tab1, tab2 = st.tabs(["🚀 종목 대시보드", "📊 전체 재무제표 (원본)"])

        with tab1:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("실시간 현재가", f"{unit}{p_format.format(current_p)}")
                st.markdown(f"""<div style="background-color: {badge_color}; padding: 5px 10px; border-radius: 5px; color: white; font-weight: bold;">{badge_icon} {badge_text}</div>""", unsafe_allow_html=True)
            with c2: st.metric("⚡ 매수 가치", f"{unit}{p_format.format(t_buy)}", f"{gap_buy:.1f}%")
            with c3: 
                st.metric("🛡️ 보수적 적정가", f"{unit}{p_format.format(t_min)}", f"{gap_min:.1f}%")
                if cagr_min: st.markdown(f"<div style='background-color:#7B1FA2;color:white;padding:3px;border-radius:3px;font-size:0.8em'>📈 7~10년 CAGR {cagr_min:+.1f}%</div>", unsafe_allow_html=True)
            with c4: 
                st.metric("🚀 최대 미래가치", f"{unit}{p_format.format(t_max)}", f"{gap_max:.1f}%")
                if cagr_max: st.markdown(f"<div style='background-color:#7B1FA2;color:white;padding:3px;border-radius:3px;font-size:0.8em'>📈 7~10년 CAGR {cagr_max:+.1f}%</div>", unsafe_allow_html=True)

            st.write("---")
            col1, col2 = st.columns(2)
            with col1: draw_chart(yf_code, "3mo", "📅 최근 3개월", unit, current_price=current_p)
            with col2: draw_chart(yf_code, "5y", "🏛️ 5년 장기", unit, t_min, t_max, t_buy)
            
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

                with st.spinner(f"DART에서 {selected}의 데이터를 가져와 정리 중입니다..."):
                    raw_df, msg = fetch_all_financials(DART_API_KEY, dart_code)
                
                if raw_df is not None:
                    # 1. 컨트롤 패널
                    col_sel1, col_sel2 = st.columns(2)
                    with col_sel1:
                        fs_options = raw_df['fs_div'].unique() 
                        fs_map = {'CFS': '연결재무제표', 'OFS': '별도재무제표'}
                        display_fs = [fs_map.get(x, x) for x in fs_options]
                        choice_fs_display = st.selectbox("1. 연결/별도 선택", display_fs)
                        choice_fs = [k for k, v in fs_map.items() if v == choice_fs_display][0] if choice_fs_display in fs_map.values() else choice_fs_display

                    with col_sel2:
                        sj_options = raw_df['sj_nm'].unique()
                        choice_sj = st.selectbox("2. 표 종류 선택", sj_options)

                    # 2. 필터링
                    mask = (raw_df['fs_div'] == choice_fs) & (raw_df['sj_nm'] == choice_sj)
                    filtered_df = raw_df[mask].copy()
                    
                    if not filtered_df.empty:
                        filtered_df = filtered_df.drop_duplicates(subset=['account_nm', 'Year'])
                        pivot_df = filtered_df.pivot(index='account_nm', columns='Year', values='thstrm_amount')
                        
                        # 단위 변환
                        pivot_df = pivot_df / 100000000
                        pivot_df = pivot_df.round(0)
                        
                        # [핵심] 3. 정렬 로직 적용! (Sort)
                        # (1) 열(Year) 정렬: 최신순 (내림차순)
                        cols = sorted(pivot_df.columns, reverse=True)
                        pivot_df = pivot_df[cols]
                        
                        # (2) 행(Account) 정렬: 표준 순서대로 (함수 호출)
                        pivot_df = sort_financial_accounts(pivot_df, choice_sj)

                        st.markdown(f"### 📊 {selected} {choice_fs_display} - {choice_sj}")
                        st.markdown("**단위: 억원** (데이터 출처: DART)")
                        st.dataframe(pivot_df, use_container_width=True, height=800)
                        
                        csv = pivot_df.to_csv().encode('utf-8-sig')
                        st.download_button("💾 엑셀 다운로드", csv, f"{selected}_재무제표.csv", "text/csv")
                        
                    else:
                        st.warning("선택하신 조건의 데이터가 없습니다.")
                else:
                    st.error(f"데이터를 가져오지 못했습니다. ({msg})")

    else:
        st.warning("종목 없음")
else:
    st.error("데이터 로딩 실패")
