import streamlit as st
import streamlit.components.v1 as components 
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
# [스타일] 네이버 증권 스타일
# ---------------------------------------------------------
st.markdown("""
<style>
    button[data-baseweb="tab"] div p { font-size: 18px !important; font-weight: bold !important; }
    thead tr th { 
        background-color: #f5f6f7 !important; 
        color: #333333 !important; 
        font-size: 14px !important; 
        font-weight: bold !important; 
        border-top: 2px solid #333 !important;
        border-bottom: 1px solid #ccc !important;
    }
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
# [정렬 엔진 1] 계정 과목(행) 정렬
# ---------------------------------------------------------
def sort_financial_accounts(df, report_type):
    if '손익' in report_type or '포괄' in report_type:
        order_list = [
            '매출액', '수익(매출액)', '영업수익', 
            '매출원가', '영업비용',
            '매출총이익',
            '판매비와관리비', '판매비및관리비', '판관비',
            '영업이익', '영업이익(손실)',
            '금융수익', '금융원가', '금융비용', '기타수익', '기타비용',
            '법인세비용차감전계속사업이익', '법인세차감전순이익',
            '법인세비용',
            '당기순이익', '당기순이익(손실)',
            '지배기업소유주지분', '지배주주지분순이익',
            '비지배지분', '비지배주주지분순이익',
            '총포괄손익'
        ]
    elif '상태' in report_type:
        order_list = [
            '자산총계', 
            '유동자산', '현금및현금성자산', '매출채권', '재고자산', 
            '비유동자산', '유형자산', '무형자산',
            '부채총계', 
            '유동부채', '매입채무', '단기차입금', 
            '비유동부채', '사채', '장기차입금',
            '자본총계', '지배기업소유주지분', '자본금', '이익잉여금'
        ]
    elif '현금' in report_type:
        order_list = [
            '영업활동현금흐름', '영업활동으로인한현금흐름',
            '당기순이익', '당기순이익(손실)', 
            '감가상각비',
            '운전자본의변동', '자산부채의변동',
            '투자활동현금흐름', '투자활동으로인한현금흐름',
            '유형자산의취득', '유형자산의처분',
            '재무활동현금흐름', '재무활동으로인한현금흐름',
            '차입금의증가', '차입금의감소', '배당금지급',
            '현금의증가', '현금의감소',
            '기초현금및현금성자산', '기말현금및현금성자산'
        ]
    else:
        return df 

    current_index = df.index.tolist()
    sorted_index = []
    
    for item in order_list:
        if item in current_index:
            sorted_index.append(item)
            
    for item in current_index:
        if item not in sorted_index:
            sorted_index.append(item)
            
    return df.reindex(sorted_index)

# ---------------------------------------------------------
# [정렬 엔진 2] 표 종류 정렬
# ---------------------------------------------------------
def sort_report_types(options):
    priority = ['포괄손익계산서', '손익계산서', '재무상태표', '현금흐름표', '자본변동표']
    def get_priority(name):
        for i, key in enumerate(priority):
            if key in name:
                return i
        return 99
    return sorted(options, key=get_priority)


# 4. DART 데이터 수집 함수 (강력한 이름 매핑 적용)
@st.cache_data(show_spinner=False) 
def fetch_all_financials(api_key, ticker_code, mode="연간"):
    try:
        dart = OpenDartReader(api_key)
    except Exception as e:
         return None, f"API 키 오류: {e}"

    if len(str(ticker_code)) != 6:
        return None, "DART 조회 불가"

    now_year = datetime.datetime.now().year
    
    if mode == "연간":
        target_codes = ['11011']
        years = range(now_year - 5, now_year + 1)
        code_map = {'11011': '연간'}
    else:
        target_codes = ['11013', '11012', '11014', '11011']
        years = range(now_year - 3, now_year + 1)
        code_map = {
            '11013': '1Q', 
            '11012': '2Q(반기)', 
            '11014': '3Q', 
            '11011': '4Q(연간)'
        }
    
    all_data_list = []
    status_text = st.empty()
    
    try:
        for year in years:
            for code in target_codes:
                label = code_map[code]
                if mode == "분기":
                    status_text.text(f"📥 {year}년 {label} 데이터 찾는 중...")
                else:
                    status_text.text(f"📥 {year}년 데이터 찾는 중...")
                
                try:
                    df = dart.finstate(ticker_code, year, reprt_code=code)
                except:
                    df = None

                if df is not None:
                    if mode == "연간":
                        period_name = str(year)
                    else:
                        period_name = f"{str(year)[2:]}.{label}"

                    df['Period'] = period_name
                    
                    # [핵심] sj_div(코드)가 없어도 sj_nm(이름)에 '현금'이 있으면 '현금흐름표'로 강제 통합
                    if 'sj_nm' in df.columns:
                        # 1. 코드 기반 매핑
                        if 'sj_div' in df.columns:
                            standard_map = {'BS':'재무상태표', 'IS':'손익계산서', 'CIS':'포괄손익계산서', 'CF':'현금흐름표', 'SCE':'자본변동표'}
                            df['sj_nm'] = df['sj_div'].map(standard_map).fillna(df['sj_nm'])
                        
                        # 2. 이름 기반 강제 매핑 (코드가 비어있을 경우 대비)
                        df.loc[df['sj_nm'].str.contains('현금흐름', na=False), 'sj_nm'] = '현금흐름표'
                        df.loc[df['sj_nm'].str.contains('재무상태', na=False), 'sj_nm'] = '재무상태표'
                        df.loc[df['sj_nm'].str.contains('포괄손익', na=False), 'sj_nm'] = '포괄손익계산서'
                        # 손익계산서는 포괄손익과 겹치지 않게 주의
                        df.loc[(df['sj_nm'].str.contains('손익계산', na=False)) & (~df['sj_nm'].str.contains('포괄', na=False)), 'sj_nm'] = '손익계산서'
                        df.loc[df['sj_nm'].str.contains('자본변동', na=False), 'sj_nm'] = '자본변동표'

                    cols = ['Period', 'fs_div', 'sj_nm', 'account_nm', 'thstrm_amount']
                    valid_cols = [c for c in cols if c in df.columns]
                    all_data_list.append(df[valid_cols])
                
                time.sleep(0.15)

        status_text.empty()

        if all_data_list:
            df_final = pd.concat(all_data_list)
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
        
        # 지표 계산
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

        tab1, tab2 = st.tabs(["🚀 종목 대시보드", "📊 재무 분석"])

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

                col_ui1, col_ui2, col_ui3 = st.columns([1, 1, 2])
                with col_ui1:
                    fs_mode = st.radio("기준", ["연결", "별도"], horizontal=True, index=0)
                    fs_code = 'CFS' if fs_mode == "연결" else 'OFS'
                with col_ui2:
                    period_mode = st.radio("기간", ["연간", "분기"], horizontal=True, index=0)

                with st.spinner(f"📊 {selected} ({period_mode}) 데이터 수집 중..."):
                    unique_key = f"{selected}_{period_mode}"
                    if 'last_key' not in st.session_state or st.session_state.last_key != unique_key:
                        fetch_all_financials.clear() 
                        st.session_state.last_key = unique_key
                        
                    raw_df, msg = fetch_all_financials(DART_API_KEY, dart_code, period_mode)
                
                with col_ui3:
                    if raw_df is not None:
                        # [필수] 종류 정렬
                        raw_options = raw_df['sj_nm'].unique()
                        sorted_options = sort_report_types(raw_options) 
                        selected_sj = st.selectbox("표 종류", sorted_options, index=0)
                    else:
                        selected_sj = None

                st.markdown("---")

                if raw_df is not None and selected_sj:
                    mask = (raw_df['fs_div'] == fs_code) & (raw_df['sj_nm'] == selected_sj)
                    filtered_df = raw_df[mask].copy()
                    
                    if not filtered_df.empty:
                        filtered_df = filtered_df.drop_duplicates(subset=['account_nm', 'Period'])
                        pivot_df = filtered_df.pivot(index='account_nm', columns='Period', values='thstrm_amount')
                        
                        pivot_df = pivot_df / 100000000
                        pivot_df = pivot_df.round(0)
                        
                        cols = sorted(pivot_df.columns, reverse=True)
                        pivot_df = pivot_df[cols]
                        
                        pivot_df = sort_financial_accounts(pivot_df, selected_sj)

                        st.markdown(f"#### 📊 {selected_sj} (단위: 억원)")
                        st.dataframe(pivot_df, use_container_width=True, height=800)
                        
                        csv = pivot_df.to_csv().encode('utf-8-sig')
                        st.download_button("💾 엑셀 다운로드", csv, f"{selected}_{selected_sj}.csv", "text/csv")
                        
                    else:
                        st.warning(f"선택하신 '{selected_sj}' 데이터가 '{fs_mode}' 기준으로는 없습니다. (만약 현금흐름표가 없다면 아래 '데이터 정밀 진단기'를 확인해주세요)")
                elif raw_df is None:
                    st.error(f"데이터를 가져오지 못했습니다. ({msg})")

                # -----------------------------------------------
                # [🔍 데이터 정밀 진단기]
                # API가 실제로 뭘 가져왔는지 뜯어보는 디버깅용 창입니다.
                # 현금흐름표가 죽어도 안 뜨면 이걸 열어서 보여주세요.
                # -----------------------------------------------
                with st.expander("🔍 데이터 정밀 진단기 (안 될 때만 열어보세요)"):
                    if raw_df is not None:
                        st.write("DART에서 감지된 표 목록 (sj_nm):", raw_df['sj_nm'].unique())
                        st.write("샘플 데이터 (상위 50행):")
                        st.dataframe(raw_df.head(50))
                    else:
                        st.write("데이터가 로드되지 않았습니다.")

    else:
        st.warning("종목 없음")
else:
    st.error("데이터 로딩 실패")
