import streamlit as st
import streamlit.components.v1 as components 
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl
import OpenDartReader
import time

# 1. 화면 설정
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. SSL 에러 방지
ssl._create_default_https_context = ssl._create_unverified_context

# 3. 데이터 로딩
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

# 4. DART 데이터 수집 함수
def fetch_dart_data(api_key, ticker_code, stock_name):
    try:
        dart = OpenDartReader(api_key)
    except Exception as e:
         return None, f"API 키 오류: {e}"

    if len(str(ticker_code)) != 6:
        return None, f"DART는 6자리 숫자 코드만 조회 가능합니다. (현재: {ticker_code})"

    start_year = 2015
    end_year = 2023
    financial_list = []
    
    progress_text = "DART 서버 접속 중..."
    my_bar = st.progress(0, text=progress_text)
    total_years = end_year - start_year + 1

    try:
        for idx, year in enumerate(range(start_year, end_year + 1)):
            percent = int((idx / total_years) * 100)
            my_bar.progress(percent, text=f"{year}년도 데이터 수집 중... ({percent}%)")
            
            # 데이터 요청
            df = dart.finstate(ticker_code, year, reprt_code='11011')
            
            if df is not None:
                df = df[df['fs_div'] == 'CFS'] # 연결재무제표
                df['Year'] = year
                
                cond_sales = df['account_nm'].str.contains('매출액|영업수익') & ~df['account_nm'].str.contains('원가')
                cond_op = df['account_nm'].str.contains('영업이익')
                cond_net = df['account_nm'].str.contains('당기순이익') & ~df['account_nm'].str.contains('포괄|지배|비지배')
                
                target_df = df[cond_sales | cond_op | cond_net].copy()
                financial_list.append(target_df)
            
            time.sleep(0.3)

        my_bar.progress(100, text="정리 중...")
        time.sleep(0.5)
        my_bar.empty()

        if financial_list:
            df_final = pd.concat(financial_list)
            df_final['thstrm_amount'] = df_final['thstrm_amount'].astype(str).str.replace(',', '').astype(float)
            df_clean = df_final[['Year', 'account_nm', 'thstrm_amount']]
            
            df_pivot = df_clean.pivot_table(index='Year', columns='account_nm', values='thstrm_amount', aggfunc='sum')
            df_pivot = df_pivot / 100000000 # 억 단위
            df_pivot = df_pivot.round(0)
            
            file_name = f"{stock_name}({ticker_code})_재무제표.csv"
            df_pivot.to_csv(file_name, encoding="utf-8-sig")
            
            return df_pivot, f"성공! '{file_name}' 저장 완료"
        else:
            return None, "데이터를 찾지 못했습니다."

    except Exception as e:
        return None, f"에러 발생: {e}"

# 5. 차트 함수
def draw_chart(ticker, period, title, unit, target_min=None, target_max=None, target_buy=None, current_price=None):
    try:
        interval = "1d" if period == "3mo" else "1wk"
        df = yf.download(ticker, period=period, interval=interval)
        if df.empty: return st.write(f"{title} 데이터 없음 (티커 확인 필요)")
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
    
    # 시장 필터링 로직 수정 (자동 인식)
    if market_choice == "한국(KRW)":
        # .KS, .KQ로 끝나거나 숫자만 있는 경우
        filtered_df = df_sheet[df_sheet['Market'] == "한국(KRW)"]
    else:
        filtered_df = df_sheet[df_sheet['Market'] == "미국(USD)"]
        
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"## 🎯 {market_choice} 종목")
    
    if not filtered_df.empty:
        selected = st.sidebar.selectbox("종목 선택 👇", filtered_df['종목명'].unique())
        s_info = filtered_df[filtered_df['종목명'] == selected].iloc[0]
        
        # --- [핵심] 티커 코드 정제 로직 (에러 해결의 열쇠 🗝️) ---
        raw_code = str(s_info['코드']).strip().upper()
        
        if market_choice == "한국(KRW)":
            # 1. DART용 코드: 숫자만 남기기 (예: "280360.KS" -> "280360")
            # 문자 제거하고 숫자만 추출
            import re
            dart_code = "".join(re.findall(r'\d+', raw_code))
            if len(dart_code) < 6: dart_code = dart_code.zfill(6) # 005930 같이 앞자리 0 채우기
            
            # 2. yfinance용 코드: 뒤에 .KS가 없으면 붙이기
            # 코스닥인지 코스피인지 모르면 일단 KS 시도 (대부분 KS)
            if raw_code.endswith(".KQ"):
                yf_code = dart_code + ".KQ"
            else:
                yf_code = dart_code + ".KS"
        else:
            # 미국주식은 그대로
            dart_code = raw_code
            yf_code = raw_code

        is_korea = market_choice == "한국(KRW)"
        unit = "₩" if is_korea else "$"
        p_format = "{:,.0f}" if is_korea else "{:,.2f}"
        
        # --- DART 데이터 수집 버튼 ---
        if is_korea:
            st.sidebar.markdown("---")
            st.sidebar.subheader("📊 재무 데이터 수집")
            
            # ⚠️ 본인의 DART API 키 확인 필수!
            DART_API_KEY = "f7626661c1cd11987d285bd50b6d94ffdc08ca62" 
            
            if st.sidebar.button("10년치 재무제표 가져오기 (클릭)"):
                with st.spinner('DART 접속 중...'):
                    # 정제된 dart_code(6자리 숫자)를 넘겨줌
                    dart_df, msg = fetch_dart_data(DART_API_KEY, dart_code, selected)
                    
                    if dart_df is not None:
                        st.sidebar.success(msg)
                        st.session_state['dart_data'] = dart_df
                    else:
                        st.sidebar.error(msg)
        
        # --- 가격 및 지표 계산 ---
        grade = s_info.get('투자등급', '미분류') 
        badge_color = {"코어": "#2962FF", "위성": "#FFAB00", "시가존": "#2E7D32"}.get(grade, "#616161")
        badge_icon = {"코어": "💎", "위성": "🛰️", "시가존": "🚬"}.get(grade, "❔")
        badge_text = {"코어": "CORE", "위성": "SATELLITE", "시가존": "시가존"}.get(grade, "미지정")

        try:
            # 정제된 yf_code 사용
            ticker_obj = yf.Ticker(yf_code)
            history = ticker_obj.history(period="1d")
            current_p = history['Close'].iloc[-1] if not history.empty else 0
            
            t_min = float(s_info.get('보수적적정가', 0))
            t_max = float(s_info.get('최대미래가치', 0))
            t_buy = float(s_info.get('매수가치', 0))
            
            gap_min = ((t_min - current_p)/current_p)*100 if current_p else 0
            gap_max = ((t_max - current_p)/current_p)*100 if current_p else 0
            gap_buy = ((t_buy - current_p)/current_p)*100 if current_p else 0
