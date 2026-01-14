import streamlit as st
import pandas as pd
import urllib.parse
from datetime import datetime
import gspread
import json
from google.oauth2.service_account import Credentials

# 1. 페이지 설정
st.set_page_config(page_title="재고 상품 관리 시스템", layout="wide")

# 구글 시트 연결 함수 (Secrets 활용 - TOML 구조 방식)
def get_google_sheet():
    try:
        # Secrets에 정의된 gcp_service_account 딕셔너리를 직접 가져옵니다.
        credentials_info = st.secrets["gcp_service_account"]
        
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds = Credentials.from_service_account_info(credentials_info, scopes=scopes)
        client = gspread.authorize(creds)
        
        # 사용자의 구글 시트 주소
        SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1n2k5EvRj_DMhkb8XWyY3-WghTfdaXFumeZkv3cnba3w/edit"
        sheet = client.open_by_url(SPREADSHEET_URL).sheet1
        return sheet
    except Exception as e:
        st.error(f"구글 인증 또는 시트 연결 오류: {e}")
        return None

st.title("🛍️ 상품 최저가 검색 및 통합 주문 시스템")

# 2. 데이터 불러오기
@st.cache_data
def load_data():
    # [cite_start]제공된 data.csv 로드 [cite: 1]
    df = pd.read_csv("data.csv")
    # [cite_start]PRICE 열 숫자 변환 (계산용) [cite: 1]
    df['PRICE_NUM'] = df['PRICE'].astype(str).str.replace(',', '').astype(float)
    # 검색용 표시 컬럼 생성
    df['Display'] = df['NC'].astype(str) + " - " + df['ItemName']
    return df

try:
    df = load_data()
    
    if 'order_mode' not in st.session_state:
        st.session_state.order_mode = False

    # --- [변경 구간: 상단] 3. 개별 상품 상세 정보 및 최저가 검색 ---
    st.subheader("🔎 개별 상품 상세 정보 및 최저가 검색")
    st.write("상품을 선택하면 상세 정보와 네이버 쇼핑 최저가를 바로 확인할 수 있습니다.")
    
    target = st.selectbox("조회할 상품을 선택하세요", df['Display'].unique(), key="detail_top")
    
    if target:
        # [cite_start]선택된 상품 정보 추출 [cite: 1]
        info = df[df['Display'] == target].iloc[0]
        
        # 상세 정보를 깔끔하게 보여주기 위해 컬럼 분할
        c1, c2 = st.columns(2)
        with c1:
            st.info(f"**상품명:** {info['ItemName']}")
            st.write(f"**브랜드:** {info['Brand']}")
            st.write(f"**모델번호:** {info['Commercial']}")
        with c2:
            st.success(f"### **실제 구매가(PRICE): {info['PRICE']}원**")
            st.write(f"**기준가(Go Price):** {info['Go Price(판매가)']}원")
            
            # 네이버 쇼핑 검색 연결
            query = urllib.parse.quote(info['ItemName'])
            search_url = f"https://search.shopping.naver.com/search/all?query={query}"
            st.link_button("🚀 네이버 쇼핑 최저가 확인하기", search_url, use_container_width=True)
    
    st.markdown("---")

    # --- [변경 구간: 하단] 4. 상품 다중 선택 및 주문 영역 ---
    st.subheader("📦 묶음 주문 (장바구니)")
    st.write("여러 상품을 한꺼번에 주문하려면 여기서 선택해 주세요.")
    
    selected_items = st.multiselect(
        "주문 목록에 담을 상품들을 선택하세요",
        df['Display'].unique(),
        key="cart_select"
    )

    if selected_items:
        basket_df = df[df['Display'].isin(selected_items)]
        
        st.write("### 🛒 현재 장바구니 내역")
        st.table(basket_df[['ItemName', 'Brand', 'Go Price(판매가)', 'PRICE']])
        
        total_price = basket_df['PRICE_NUM'].sum()
        st.warning(f"**총 주문 예정 금액: {total_price:,.0f}원**")

        if st.button("📝 주문서 작성하기", use_container_width=True):
            st.session_state.order_mode = True

    # 5. 배송 정보 입력 및 전송
    if st.session_state.order_mode and selected_items:
        st.markdown("---")
        st.subheader("🚚 최종 주문 정보 입력")
        
        with st.form("order_submission_form"):
            user_name = st.text_input("주문자 성함")
            user_address = st.text_area("배송지 주소")
            user_phone = st.text_input("연락처")
            
            submit = st.form_submit_button("주문 완료 및 시트 전송")
            
            if submit:
                if user_name and user_address and user_phone:
                    sheet = get_google_sheet()
                    if sheet:
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        items_str = ", ".join(basket_df['ItemName'].tolist())
                        final_amt = f"{basket_df['PRICE_NUM'].sum():,.0f}원"
                        
                        # 시트에 데이터 기록
                        sheet.append_row([now, user_name, user_phone, user_address, items_str, final_amt])
                        
                        st.balloons()
                        st.success("✅ 주문 기록이 구글 시트에 성공적으로 업데이트되었습니다!")
                        st.session_state.order_mode = False
                else:
                    st.warning("배송 정보를 모두 입력해 주세요.")

except Exception as e:
    st.error(f"애플리케이션 실행 중 오류가 발생했습니다: {e}")
