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
        
        # 지정된 시트 주소
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
    # PRICE 열 숫자 변환
    df['PRICE_NUM'] = df['PRICE'].astype(str).str.replace(',', '').astype(float)
    df['Display'] = df['NC'].astype(str) + " - " + df['ItemName']
    return df

try:
    df = load_data()
    
    # 장바구니 세션 관리 {상품ID: 수량}
    if 'cart' not in st.session_state:
        st.session_state.cart = {}
    if 'order_mode' not in st.session_state:
        st.session_state.order_mode = False

    # --- [상단] 3. 상품 탐색 영역 ---
    st.subheader("🔎 1. 상품 선택")
    
    all_options = df['Display'].unique()
    selected_target = st.selectbox(
        "상품을 선택하여 상세 정보를 확인하세요",
        all_options,
        index=None,
        placeholder="여기를 눌러 상품 찾기",
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
                st.success(f"### **구매가: {info['PRICE']}원**")
            
            # 담기 전 초기 수량 설정
            order_qty = st.number_input("추가할 수량", min_value=1, value=1, step=1, key="add_qty_input")
            
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                q = urllib.parse.quote(info['ItemName'])
                st.link_button("🚀 네이버 최저가 확인", f"https://search.shopping.naver.com/search/all?query={q}", use_container_width=True)
            with btn_col2:
                if st.button("🛒 주문 목록에 담기", use_container_width=True):
                    if selected_target in st.session_state.cart:
                        st.session_state.cart[selected_target] += order_qty
                    else:
                        st.session_state.cart[selected_target] = order_qty
                    st.toast(f"목록에 {order_qty}개 추가되었습니다!")

    st.markdown("---")

    # --- [하단] 4. 내 주문 목록 (수량 직접 수정 기능) ---
    st.subheader("📦 2. 내 주문 목록 (수량 수정 가능)")
    
    if st.session_state.cart:
        total_p = 0
        
        # 목록을 돌면서 수량 수정 UI 배치
        for item_id, current_qty in list(st.session_state.cart.items()):
            item_info = df[df['Display'] == item_id].iloc[0]
            
            with st.container(border=False):
                col_name, col_qty, col_del = st.columns([3, 1.5, 0.5])
                
                # 1. 상품명 표시
                col_name.write(f"**{item_info['ItemName']}**\n({item_info['PRICE']}원)")
                
                # 2. 수량 직접 수정 (변경 즉시 세션 업데이트)
                new_qty = col_qty.number_input(
                    "수량", 
                    min_value=1, 
                    value=current_qty, 
                    key=f"edit_{item_id}", 
                    label_visibility="collapsed"
                )
                if new_qty != current_qty:
                    st.session_state.cart[item_id] = new_qty
                    st.rerun() # 수량 변경 시 즉시 합계 재계산
                
                # 3. 삭제 버튼
                if col_del.button("❌", key=f"del_{item_id}"):
                    del st.session_state.cart[item_id]
                    st.rerun()
                
                # 소계 계산 및 표시
                subtotal = item_info['PRICE_NUM'] * st.session_state.cart[item_id]
                total_p += subtotal
                st.write(f"소계: **{subtotal:,.0f}원**")
                st.divider()

        st.warning(f"### **최종 합계 금액: {total_p:,.0f}원**")
        
        c1, c2 = st.columns(2)
        if c1.button("🗑️ 전체 비우기", use_container_width=True):
            st.session_state.cart = {}
            st.session_state.order_mode = False
            st.rerun()
            
        if c2.button("📝 주문서 작성하기", use_container_width=True):
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
                            
                            summary = []
                            for d, q in st.session_state.cart.items():
                                itm = df[df['Display'] == d].iloc[0]['ItemName']
                                summary.append(f"{itm}({q}개)")
                            items_summary = ", ".join(summary)
                            
                            sheet.append_row([now, name, phone, addr, items_summary, f"{total_p:,.0f}원"])
                            st.balloons()
                            st.success("✅ 주문이 완료되었습니다!")
                            st.session_state.cart = {}
                            st.session_state.order_mode = False
                    else:
                        st.error("배송 정보를 모두 입력해 주세요.")
    else:
        st.info("주문 목록에 담긴 상품이 없습니다.")

except Exception as e:
    st.error(f"애플리케이션 오류: {e}")
