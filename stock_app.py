# [수정됨] 회사 개요 정보 가져오기, 번역 및 '자동 문단 나누기'
            # -----------------------------------------------
            summary_text = "회사 정보를 가져오는 중입니다..."
            try:
                raw_summary = ticker_obj.info.get('longBusinessSummary', '')
                if raw_summary:
                    # 1. 번역 실행 (최대 3000자까지만 끊어서 번역 - 오류 방지)
                    translated_text = GoogleTranslator(source='auto', target='ko').translate(raw_summary[:3000])
                    
                    # 2. '벽돌 텍스트'를 문단으로 나누기 (파이썬 문자열 처리)
                    # ". " (마침표+공백)을 기준으로 문장을 자릅니다.
                    sentences = translated_text.split('. ')
                    
                    formatted_text = ""
                    for i, sentence in enumerate(sentences):
                        # 문장 끝에 마침표가 없으면 다시 붙여줍니다.
                        clean_sentence = sentence.strip()
                        if not clean_sentence.endswith('.'):
                            clean_sentence += "."
                        
                        formatted_text += clean_sentence + " "
                        
                        # 3. 문장 2~3개마다 줄바꿈(<br>)을 추가하여 가독성을 높입니다.
                        if (i + 1) % 3 == 0:
                            formatted_text += "<br><br>"
                    
                    summary_text = formatted_text
                else:
                    summary_text = "제공된 회사 개요 정보가 없습니다."
            except Exception as e:
                summary_text = f"회사 개요를 불러오지 못했습니다. ({str(e)})"
            # -----------------------------------------------

            # [수정됨] CSS 스타일 강화 (줄간격 1.6, 양쪽 정렬)
            st.markdown(f"""
            <div class="summary-box" style="line-height: 1.8; text-align: justify; font-size: 15px;">
                <b style="font-size: 18px; color: #FFAB00;">🏢 {selected} 기업 개요</b> <span style="font-size: 12px; color: gray;">(AI 자동 번역 & 요약)</span><br><br>
                {summary_text}
            </div>
            """, unsafe_allow_html=True)
