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
    df = pd.read_csv("data.csv")
    df['PRICE_NUM'] = df['PRICE'].astype(str).str.replace(',', '').astype(float)
    df['Display'] = df['NC'].astype(str) + " - " + df['ItemName']
    return df

try:
    df = load_data()
    
    # 세션 상태 초기화
    if 'cart' not in st.session_state:
        st.session_state.cart = []
    if 'order_mode' not in st.session_state:
        st.session_state.order_mode = False

    # --- [상단] 3. 상품 탐색 및 검색 영역 ---
    st.subheader("🔎 1. 상품 탐색 및 검색")
    
    search_keyword = st.text_input("💡 검색어를 입력하면 목록이 필터링됩니다.", "")
    
    if search_keyword:
        filtered_options = df[df['ItemName'].str.contains(search_keyword, case=False) | 
                              df['Brand'].str.contains(search_keyword, case=False)]['Display'].unique()
    else:
        filtered_options = df['Display'].unique()

    selected_target = st.selectbox(
        f"상품을 선택하세요 ({len(filtered_options)}개)",
        filtered_options,
        index=None,
        placeholder="상품을 선택하거나 입력하세요",
        key="main_selector"
    )

    if selected_target:
        info = df[df['Display'] == selected_target].iloc[0]
        
        with st.container(border=True):
            st.info(f"**{info['ItemName']}**")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**브랜드:** {info['Brand']}")
                st.write(f"**모델:** {info['Commercial']}")
            with col2:
                st.success(f"### **실제 구매가: {info['PRICE']}원**")
            
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

    # --- [하단] 4. 장바구니 관리 (개별 삭제 추가) ---
    st.subheader("📦 2. 내 주문 목록")
    
    if st.session_state.cart:
        # 담긴 상품들을 리스트로 보여주고 옆에 삭제 버튼 배치
        total_p = 0
        for i, item_display in enumerate(st.session_state.cart):
            item_info = df[df['Display'] == item_display].iloc[0]
            total_p += item_info['PRICE_NUM']
            
            # 모바일에서 누르기 쉬운 리스트 형태
            cart_col1, cart_col2 = st.columns([4, 1])
            cart_col1.write(f"**{item_info['ItemName']}** \n({item_info['PRICE']}원)")
            if cart_col2.button("❌", key=f"del_{i}", help="삭제"):
                st.session_state.cart.remove(item_display)
                st.rerun()
            st.divider()

        st.warning(f"**총 합계 금액: {total_p:,.0f}원**")
        
        c1, c2 = st.columns(2)
        if c1.button("🗑️ 전체 비우기", use_container_width=True):
            st.session_state.cart = []
            st.rerun()
            
        if c2.button("📝 주문서 작성", use_container_width=True):
            st.session_state.order_mode = True

        # 5. 주문 양식
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
                            st.session_state.cart = []
                            st.session_state.order_mode = False
                    else:
                        st.error("배송 정보를 입력해 주세요.")
    else:
        st.info("주문 목록이 비어 있습니다.")

except Exception as e:
    st.error(f"오류: {e}")
