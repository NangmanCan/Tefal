import streamlit as st
import pandas as pd
import urllib.parse
from datetime import datetime
import gspread
import json
from google.oauth2.service_account import Credentials

# 1. 페이지 설정
st.set_page_config(page_title="재고 상품 주문 시스템", layout="wide")

# 구글 시트 연결 함수 (Secrets 활용)
def get_google_sheet():
    # Secrets에 저장된 JSON 문자열 로드
    json_info = st.secrets["google_service_account_json"]
    credentials_info = json.loads(json_info)
    
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds = Credentials.from_service_account_info(credentials_info, scopes=scopes)
    client = gspread.authorize(creds)
    
    # [중요] 본인의 구글 시트 URL로 반드시 변경하세요!
    SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1n2k5EvRj_DMhkb8XWyY3-WghTfdaXFumeZkv3cnba3w/edit?gid=0#gid=0"
    sheet = client.open_by_url(SPREADSHEET_URL).sheet1
    return sheet

st.title("🛍️ 상품 선택 및 실시간 주문 시스템")

# 2. 데이터 불러오기
@st.cache_data
def load_data():
    df = pd.read_csv("data.csv")
    # PRICE 열에서 콤마 제거 후 숫자형 변환 (계산용)
    df['PRICE_NUM'] = df['PRICE'].replace('[\,]', '', regex=True).astype(float)
    return df

try:
    df = load_data()
    
    if 'show_order_form' not in st.session_state:
        st.session_state.show_order_form = False

    # 3. 상품 다중 선택 영역
    st.subheader("🔍 1. 상품 선택")
    df['Display'] = df['NC'].astype(str) + " - " + df['ItemName']
    
    selected_items = st.multiselect(
        "주문할 상품들을 선택하세요 (복수 선택 가능)",
        df['Display'].unique()
    )

    if selected_items:
        current_selection = df[df['Display'].isin(selected_items)]
        
        st.write("### 🛒 선택된 상품 목록")
        st.dataframe(current_selection[['ItemName', 'Brand', 'Go Price(판매가)', 'PRICE']], use_container_width=True)
        
        total_price = current_selection['PRICE_NUM'].sum()
        st.success(f"**총 주문 예정 금액: {total_price:,.0f}원** (실제 구매가 합계)")

        if st.button("📝 주문서 작성하기"):
            st.session_state.show_order_form = True

    # 4. 주문 정보 입력 및 구글 시트 전송
    if st.session_state.show_order_form and selected_items:
        st.markdown("---")
        st.subheader("🚚 2. 배송 정보 입력")
        
        with st.form("google_order_form"):
            name = st.text_input("주문자 성함")
            phone = st.text_input("연락처 (010-0000-0000)")
            address = st.text_area("배송지 주소")
            
            submit_button = st.form_submit_button("최종 주문 완료")
            
            if submit_button:
                if name and phone and address:
                    try:
                        # 데이터 준비
                        order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        item_names = " | ".join(current_selection['ItemName'].tolist())
                        total_amt = f"{current_selection['PRICE_NUM'].sum():,.0f}원"
                        
                        # 구글 시트 연결
                        sheet = get_google_sheet()
                        
                        # 헤더가 없으면 추가
                        if not sheet.get_all_values():
                            sheet.append_row(["주문일시", "주문자", "연락처", "주소", "주문상품", "총결제금액"])
                        
                        # 데이터 행 추가
                        sheet.append_row([order_date, name, phone, address, item_names, total_amt])
                        
                        st.balloons()
                        st.success("✅ 주문이 성공적으로 완료되어 구글 시트에 기록되었습니다!")
                        st.session_state.show_order_form = False
                    except Exception as e:
                        st.error(f"구글 시트 전송 실패: {e}")
                else:
                    st.warning("모든 필수 정보를 입력해 주세요.")

    # 5. 기존 네이버 검색 기능 (하단 유지)
    st.markdown("---")
    with st.expander("🔎 개별 상품 네이버 최저가 확인"):
        search_option = st.selectbox("상품을 골라보세요", df['Display'].unique())
        if search_option:
            prod = df[df['Display'] == search_option].iloc[0]
            st.write(f"**선택 상품:** {prod['ItemName']}")
            st.write(f"**실제 구매가:** {prod['PRICE']}원")
            encoded_q = urllib.parse.quote(prod['ItemName'])
            st.markdown(f"[🔗 네이버 쇼핑에서 검색 결과 보기](https://search.shopping.naver.com/search/all?query={encoded_q})")

except Exception as e:
    st.error(f"시스템 오류 발생: {e}")
