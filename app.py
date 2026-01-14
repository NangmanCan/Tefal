import streamlit as st
import pandas as pd
import urllib.parse

# 1. 페이지 설정
st.set_page_config(page_title="재고 상품 가격 검색기", layout="centered")

st.title("🛍️ 상품명 기반 네이버 쇼핑 검색기")
st.write("ItemName 전문을 사용하여 실시간 최저가를 더 정확하게 검색합니다.")

# 2. 데이터 불러오기
@st.cache_data
def load_data():
    # CSV 파일을 읽어옵니다. (인코딩 에러 방지용 utf-8-sig)
    return pd.read_csv("data.csv")

try:
    df = load_data()
    
    # 3. 사이드바 - 검색 옵션
    st.sidebar.header("검색 옵션")
    
    # 선택을 돕기 위해 '번호 + 상품명' 형태의 선택박스 생성
    df['Display'] = df['NC'].astype(str) + " - " + df['ItemName']
    
    selected_option = st.selectbox(
        "검색할 상품을 선택하세요",
        df['Display'].unique()
    )

    # 4. 선택한 상품 정보 매칭
    if selected_option:
        selected_nc = int(selected_option.split(" - ")[0])
        product_info = df[df['NC'] == selected_nc].iloc[0]

        st.markdown("---")
        st.subheader("📦 상품 상세 정보")
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**상품명:** {product_info['ItemName']}")
            st.write(f"**브랜드:** {product_info['Brand']}")
            st.write(f"**모델번호:** {product_info['Commercial']}")

        with col2:
            # 실제 구매가(PRICE)를 강조하여 표시
            st.success(f"### **실제 구매가: {product_info['PRICE']}원**")
            # 기준가(Go Price)를 보조 정보로 표시
            st.write(f"**기준가(Go Price):** {product_info['Go Price(판매가)']}원")
            st.caption("※ '실제 구매가'는 앱 내 결제 시 적용되는 가격입니다.")

        # 5. 검색 쿼리 최적화
        search_query = product_info['ItemName']
        encoded_query = urllib.parse.quote(search_query)
        naver_url = f"https://search.shopping.naver.com/search/all?query={encoded_query}"

        # 6. 네이버 쇼핑 검색 버튼
        st.markdown(f"""
            <a href="{naver_url}" target="_blank" style="text-decoration: none;">
                <div style="
                    width: 100%;
                    background-color: #03C75A;
                    color: white;
                    padding: 15px;
                    border-radius: 8px;
                    text-align: center;
                    font-size: 18px;
                    font-weight: bold;
                    cursor: pointer;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    🚀 네이버 쇼핑에서 '{search_query[:15]}...' 검색
                </div>
            </a>
            """, unsafe_allow_html=True)
        
        st.caption("※ 버튼을 클릭하면 새로운 창에서 네이버 쇼핑 검색 결과가 열립니다.")

except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
