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
            col1, col2
