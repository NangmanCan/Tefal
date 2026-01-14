import streamlit as st
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="재고 상품 가격 검색기", layout="centered")

st.title("🛍️ 상품 네이버 쇼핑 검색기")
st.write("데이터베이스에서 상품을 선택하면 네이버 최저가 검색 링크를 생성합니다.")

# 2. 데이터 불러오기 (캐싱을 사용하여 속도 향상)
@st.cache_data
def load_data():
    # CSV 파일 읽기 (인코딩 에러 방지를 위해 utf-8-sig 사용 권장)
    return pd.read_csv("data.csv")

try:
    df = load_data()
    
    # 3. 사이드바 - 검색 옵션
    st.sidebar.header("검색 옵션")
    
    # NC(번호)와 상품명을 합쳐서 선택하기 쉽게 만듦
    # 예: "1 - 테팔 풀오토..." 형태
    df['Display'] = df['NC'].astype(str) + " - " + df['ItemName']
    
    selected_option = st.selectbox(
        "검색할 상품을 선택하세요 (번호 - 상품명)",
        df['Display'].unique()
    )

    # 4. 선택한 상품 정보 보여주기
    if selected_option:
        # 선택한 문자열에서 맨 앞의 숫자(NC)만 추출해서 해당 행 찾기
        selected_nc = int(selected_option.split(" - ")[0])
        product_info = df[df['NC'] == selected_nc].iloc[0]

        st.markdown("---")
        st.subheader("📦 선택한 상품 정보")
        
        # 보기 좋게 컬럼 나누기
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**모델명:** {product_info['Commercial']}")
            st.write(f"**브랜드:** {product_info['Brand']}")
        with col2:
            st.success(f"**현재 판매가:** {product_info['Go Price(판매가)']}")
            st.write(f"**유형:** {product_info['Type']}")

        # 5. 네이버 쇼핑 검색 버튼/링크 생성
        # 검색어는 '브랜드 + 모델명' 조합이 가장 정확함
        search_query = f"{product_info['Brand']} {product_info['Commercial']}"
        naver_url = f"https://search.shopping.naver.com/search/all?query={search_query}"

        st.markdown(f"""
            <a href="{naver_url}" target="_blank">
                <button style="
                    width: 100%;
                    background-color: #03C75A;
                    color: white;
                    padding: 15px;
                    border: none;
                    border-radius: 5px;
                    font-size: 16px;
                    cursor: pointer;
                    font-weight: bold;">
                    👉 네이버 쇼핑에서 실시간 가격 확인하기
                </button>
            </a>
            """, unsafe_allow_html=True)

except FileNotFoundError:
    st.error("data.csv 파일을 찾을 수 없습니다. 같은 폴더에 엑셀 데이터를 csv로 저장해주세요.")