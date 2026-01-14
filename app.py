import streamlit as st
import pandas as pd
import urllib.parse
from datetime import datetime
import gspread
import json
from google.oauth2.service_account import Credentials

# 1. 페이지 설정
st.set_page_config(page_title="재고 상품 주문 시스템", layout="wide")

# 구글 시트 연결 함수
def get_google_sheet():
    try:
        # Streamlit Secrets에서 서비스 계정 정보 로드
        json_info = st.secrets["google_service_account_json"].strip()
        credentials_info = json.loads(json_info)
        
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds = Credentials.from_service_account_info(credentials_info, scopes=scopes)
        client = gspread.authorize(creds)
        
        # 제공해주신 시트 주소 적용
        SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1n2k5EvRj_DMhkb8XWyY3-WghTfdaXFumeZkv3cnba3w/edit"
        sheet = client.open_by_url(SPREADSHEET_URL).sheet1
        return sheet
    except Exception as e:
        st.error(f"구글 인증 또는 시트 연결 오류: {e}")
        return None

st.title("🛍️ 상품 검색 및 실시간 주문 시스템")

# 2. 데이터 불러오기
@st.cache_data
def load_data():
    # 데이터 구조: NC, CMMF Code, Commercial, ItemName, Brand, Type, Go Price(판매가), PRICE 
    df = pd.read_csv("data.csv")
    # PRICE 열에서 콤마 제거 후 숫자형으로 변환 (계산용) 
    df['PRICE_NUM'] = df['PRICE'].astype(str).str.replace(',', '').astype(float)
    return df

try:
    df = load_data()
    
    if 'order_mode' not in st.session_state:
        st.session_state.order_mode = False

    # 3. 상품 다중 선택 영역
    st.subheader("📦 상품 선택 및 장바구니")
    df['Display'] = df['NC'].astype(str) + " - " + df['ItemName']
    
    selected_items = st.multiselect(
        "주문할 상품들을 선택하세요 (복수 선택 가능)",
        df['Display'].unique()
    )

    if selected_items:
        basket_df = df[df['Display'].isin(selected_items)]
        
        st.write("### 🛒 선택된 상품 내역")
        # 실제 사용자 구매 가격(PRICE) 표시 
        st.table(basket_df[['ItemName', 'Brand', 'Go Price(판매가)', 'PRICE']])
        
        total_price = basket_df['PRICE_NUM'].sum()
        st.success(f"**총 주문 예정 금액: {total_price:,.0f}원** (PRICE 합계)")

        if st.button("📝 주문서 작성하기"):
            st.session_state.order_mode = True

    # 4. 배송 정보 입력 및 구글 시트 전송
    if st.session_state.order_mode and selected_items:
        st.markdown("---")
        st.subheader("🚚 배송 정보 입력")
        
        with st.form("order_submission_form"):
            user_name = st.text_input("주문자 성함")
            user_address = st.text_area("배송지 주소")
            user_phone = st.text_input("연락처")
            
            submit = st.form_submit_button("최종 주문 완료")
            
            if submit:
                if user_name and user_address and user_phone:
                    sheet = get_google_sheet()
                    if sheet:
                        # 데이터 기록 준비
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        items_str = ", ".join(basket_df['ItemName'].tolist())
                        final_amt = f"{basket_df['PRICE_NUM'].sum():,.0f}원"
                        
                        # 시트 하단에 데이터 추가
                        # 헤더가 없는 경우 대비
                        if not sheet.get_all_values():
                            sheet.append_row(["주문일시", "주문자", "연락처", "주소", "주문상품", "총결제금액"])
                        
                        sheet.append_row([now, user_name, user_phone, user_address, items_str, final_amt])
                        
                        st.balloons()
                        st.success("✅ 주문이 완료되었습니다! 구글 시트를 확인해 주세요.")
                        st.session_state.order_mode = False
                else:
                    st.warning("모든 필수 정보를 입력해 주세요.")

    # 5. 기존 네이버 쇼핑 검색 기능 유지
    st.markdown("---")
    with st.expander("🔎 개별 상품 상세 정보 및 최저가 검색"):
        target = st.selectbox("상품을 선택하세요", df['Display'].unique(), key="detail")
        if target:
            info = df[df['Display'] == target].iloc[0]
            st.write(f"**상품명:** {info['ItemName']}")
            st.write(f"**실제 구매가(PRICE):** {info['PRICE']}원") # PRICE 정보 표시 
            
            query = urllib.parse.quote(info['ItemName'])
            st.link_button("🚀 네이버 쇼핑 최저가 확인", f"https://search.shopping.naver.com/search/all?query={query}")

except Exception as e:
    st.error(f"오류가 발생했습니다: {e}")
