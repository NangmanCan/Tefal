import streamlit as st
import pandas as pd
import urllib.parse
from datetime import datetime
import gspread
import json
from google.oauth2.service_account import Credentials

# 1. 페이지 설정
st.set_page_config(page_title="재고 상품 관리 시스템", layout="wide")

# 구글 시트 연결 함수
def get_google_sheet():
    try:
        credentials_info = st.secrets["gcp_service_account"]
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(credentials_info, scopes=scopes)
        client = gspread.authorize(creds)
        
        SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1n2k5EvRj_DMhkb8XWyY3-WghTfdaXFumeZkv3cnba3w/edit"
        sheet = client.open_by_url(SPREADSHEET_URL).sheet1
        return sheet
    except Exception as e:
        st.error(f"구글 인증 오류: {e}")
        return None

st.title("🛍️ 상품 탐색 및 통합 주문 시스템")

# 2. 데이터 불러오기
@st.cache_data
def load_data():
    # 데이터 로드 및 전처리
    df = pd.read_csv("data.csv")
    df['PRICE_NUM'] = df['PRICE'].astype(str).str.replace(',', '').astype(float)
    df['Display'] = df['NC'].astype(str) + " - " + df['ItemName']
    return df

try:
    df = load_data()
    
    # 세션 상태 초기화 (장바구니 및 주문 모드)
    if 'cart' not in st.session_state:
        st.session_state.cart = []
    if 'order_mode' not in st.session_state:
        st.session_state.order_mode = False

    # --- [상단] 3. 상품 탐색 영역 ---
    st.subheader("🔎 1. 상품 선택")
    
    # 검색 필터 없이 전체 목록을 바로 드롭다운으로 보여줍니다.
    all_options = df['Display'].unique()
    selected_target = st.selectbox(
        f"전체 {len(all_options)}개 상품 중 하나를 선택하세요",
        all_options,
        index=None,
        placeholder="여기를 눌러 상품을 찾아보세요",
        key="main_selector"
    )

    # 선택된 상품의 상세 정보 카드
    if selected_target:
        info = df[df['Display'] == selected_target].iloc[0]
        
        with st.container(border=True):
            st.info(f"**{info['ItemName']}**")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**브랜드:** {info['Brand']}")
                st.write(f"**모델:** {info['Commercial']}")
            with col2:
                st.success(f"### **구매가: {info['PRICE']}원**")
            
            # 버튼 영역
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                q = urllib.parse.quote(info['ItemName'])
                st.link_button("🚀 네이버 최저가 확인", f"https://search.shopping.naver.com/search/all?query={q}", use_container_width=True)
            with btn_col2:
                if st.button("🛒 주문 목록에 담기", use_container_width=True):
                    if selected_target not in st.session_state.cart:
                        st.session_state.cart.append(selected_target)
                        st.toast("목록에 추가되었습니다!")

    st.markdown("---")

    # --- [하단] 4. 내 주문 목록 (장바구니 및 개별 삭제) ---
    st.subheader("📦 2. 내 주문 목록")
    
    if st.session_state.cart:
        total_p = 0
        # 장바구니 리스트 출력
        for i, item_display in enumerate(st.session_state.cart):
            item_info = df[df['Display'] == item_display].iloc[0]
            total_p += item_info['PRICE_NUM']
            
            cart_col1, cart_col2 = st.columns([4, 1])
            cart_col1.write(f"**{item_info['ItemName']}** ({item_info['PRICE']}원)")
            # 모바일에서 누르기 쉬운 X 버튼
            if cart_col2.button("❌", key=f"del_{i}"):
                st.session_state.cart.remove(item_display)
                st.rerun()
            st.divider()

        st.warning(f"**총 합계 금액: {total_p:,.0f}원**")
        
        c1, c2 = st.columns(2)
        if c1.button("🗑️ 목록 비우기", use_container_width=True):
            st.session_state.cart = []
            st.session_state.order_mode = False
            st.rerun()
            
        if c2.button("📝 주문서 작성", use_container_width=True):
            st.session_state.order_mode = True

        # 5. 주문 정보 입력 양식
        if st.session_state.order_mode:
            st.markdown("---")
            with st.form("final_order_form"):
                name = st.text_input("주문자 성함")
                addr = st.text_area("배송지 주소")
                phone = st.text_input("연락처")
                
                if st.form_submit_button("최종 주문 완료", use_container_width=True):
                    if name and addr and phone:
                        sheet = get_google_sheet()
                        if sheet:
                            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            basket_items = df[df['Display'].isin(st.session_state.cart)]
                            items_names = ", ".join(basket_items['ItemName'].tolist())
                            sheet.append_row([now, name, phone, addr, items_names, f"{total_p:,.0f}원"])
                            st.balloons()
                            st.success("✅ 주문이 완료되었습니다!")
                            # 주문 성공 후 카트 비우기
                            st.session_state.cart = []
                            st.session_state.order_mode = False
                    else:
                        st.error("배송 정보를 모두 입력해 주세요.")
    else:
        st.info("현재 주문 목록에 담긴 상품이 없습니다.")

except Exception as e:
    st.error(f"애플리케이션 오류: {e}")
