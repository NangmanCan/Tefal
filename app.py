import streamlit as st
import cloudscraper
import json
import random
import re
from difflib import SequenceMatcher
from collections import Counter

st.set_page_config(page_title="올리브영 리뷰 생성기", layout="wide")
st.title("🧴 올리브영 리뷰 생성기")
st.caption("상품명을 입력하면 올리브영에서 유사 상품을 찾아 리뷰를 조합해 새로운 리뷰를 만들어드립니다.")

# ─── Constants ───
SEARCH_API = "https://www.oliveyoung.co.kr/store/search/NewMainSearchApi.do"
IMG_BASE = "https://image.oliveyoung.co.kr/cfimages/cf-goods/uploads/images/thumbnails/"
PRODUCT_URL = "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo="


# ─── HTTP Client ───
BROWSER_CONFIGS = [
    {"browser": {"browser": "firefox", "platform": "windows", "desktop": True}},
    {"browser": {"browser": "firefox", "platform": "linux", "desktop": True}},
    {"browser": {"browser": "firefox", "platform": "darwin", "desktop": True}},
]


def create_scraper():
    """매 요청마다 새로운 scraper 생성 (Firefox UA만 사용)"""
    config = random.choice(BROWSER_CONFIGS)
    scraper = cloudscraper.create_scraper(**config)
    scraper.headers.update({
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    return scraper


# ─── API Functions ───
def search_oliveyoung(query, count=20, max_retries=4):
    """올리브영 검색 API 호출 (재시도 포함)"""
    last_error = None

    for attempt in range(max_retries):
        try:
            scraper = create_scraper()

            # 먼저 메인 페이지 방문하여 Cloudflare 쿠키 획득
            main_resp = scraper.get(
                "https://www.oliveyoung.co.kr/store/main/main.do",
                timeout=15,
            )

            # 검색 API 호출
            resp = scraper.post(
                SEARCH_API,
                data={
                    "query": query,
                    "listnum": count,
                    "startCount": 0,
                    "sort": "",
                    "displayMediaTypes": "02",
                },
                headers={
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": "https://www.oliveyoung.co.kr/store/search/getSearchMain.do",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            products = []
            for collection in data.get("Data", []):
                if collection.get("CollName") == "OLIVE_GOODS":
                    for item in collection.get("Result", []):
                        products.append({
                            "goods_no": item.get("GOODS_NO", ""),
                            "name": item.get("GOODS_NM", ""),
                            "brand": item.get("ONL_BRND_NM", ""),
                            "price": item.get("SALE_PRC", 0),
                            "original_price": item.get("NORM_PRC", 0),
                            "rating": item.get("GOODS_EVAL_SCR_VAL", 0),
                            "review_count": item.get("PRMUM_GDAS_TOT_CNT", 0),
                            "image": IMG_BASE + item.get("IMG_PATH_NM", ""),
                            "category": item.get("MID_CAT_NM", ""),
                        })
            return products
        except Exception as e:
            last_error = e
            import time
            wait = 2 ** attempt
            if attempt < max_retries - 1:
                time.sleep(wait)
            continue

    st.error(f"검색 오류 ({max_retries}회 시도 실패): {last_error}")
    return []


def calculate_similarity(query, product_name):
    """쿼리와 상품명 사이의 유사도 계산"""
    query_clean = re.sub(r"[^\w\s]", "", query.lower())
    name_clean = re.sub(r"[^\w\s]", "", product_name.lower())

    # SequenceMatcher 유사도
    seq_ratio = SequenceMatcher(None, query_clean, name_clean).ratio()

    # 키워드 매칭 점수
    query_words = set(query_clean.split())
    name_words = set(name_clean.split())
    if query_words:
        keyword_ratio = len(query_words & name_words) / len(query_words)
    else:
        keyword_ratio = 0

    return round((seq_ratio * 0.4 + keyword_ratio * 0.6) * 100, 1)


# ─── Review Generation ───
def split_sentences(text):
    """텍스트를 문장 단위로 분리"""
    sentences = re.split(r"(?<=[.!?~])\s+|(?<=다)\s+|(?<=요)\s+|(?<=음)\s+|\n+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 5]


def categorize_sentences(sentences):
    """문장을 카테고리별로 분류"""
    categories = {
        "purchase": [],   # 구매/배송 관련
        "texture": [],    # 발림성/텍스처
        "effect": [],     # 효과/결과
        "scent": [],      # 향/냄새
        "general": [],    # 일반 사용감
        "recommend": [],  # 추천/재구매
    }

    rules = {
        "purchase": ["구매", "주문", "배송", "샀", "사서", "받았", "도착", "배달", "구입", "재구매"],
        "texture": ["발림", "텍스처", "질감", "흡수", "끈적", "촉촉", "가벼", "무거", "밀림", "들뜸", "커버", "밀착"],
        "effect": ["효과", "피부", "보습", "건조", "좋아", "개선", "밝아", "탄력", "윤기", "촉촉", "수분", "진정", "트러블"],
        "scent": ["향", "냄새", "무향", "향기"],
        "recommend": ["추천", "재구매", "만족", "최고", "좋습니다", "강추", "대박", "최애", "존좋", "갓", "인생"],
    }

    for sent in sentences:
        matched = False
        for cat, keywords in rules.items():
            if any(k in sent for k in keywords):
                categories[cat].append(sent)
                matched = True
                break
        if not matched:
            categories["general"].append(sent)

    return categories


def generate_reviews(reviews_text, count=3):
    """기존 리뷰 텍스트에서 새로운 리뷰를 생성"""
    all_sentences = []
    for review in reviews_text:
        all_sentences.extend(split_sentences(review))

    if len(all_sentences) < 3:
        return ["리뷰 데이터가 부족합니다. 더 많은 리뷰를 입력해주세요."]

    categories = categorize_sentences(all_sentences)

    generated = []
    category_order = ["purchase", "texture", "effect", "scent", "general", "recommend"]

    for _ in range(count):
        parts = []
        used_cats = []

        # 각 카테고리에서 랜덤으로 문장 선택
        for cat in category_order:
            cat_sents = categories[cat]
            if cat_sents and random.random() > 0.3:  # 70% 확률로 카테고리 포함
                sent = random.choice(cat_sents)
                if sent not in parts:
                    parts.append(sent)
                    used_cats.append(cat)

        # 최소 3문장 보장
        while len(parts) < 3:
            sent = random.choice(all_sentences)
            if sent not in parts:
                parts.append(sent)

        # 최대 6문장으로 제한
        if len(parts) > 6:
            parts = parts[:6]

        # 문장 연결
        review_text = " ".join(parts)

        # 마지막 문장 부호 정리
        review_text = review_text.rstrip()
        if review_text and review_text[-1] not in ".!?~":
            review_text += "."

        generated.append(review_text)

    return generated


def extract_keywords(reviews_text, top_n=15):
    """리뷰에서 자주 등장하는 키워드 추출"""
    stopwords = {
        "그리고", "하지만", "그래서", "이", "그", "저", "것", "수", "등",
        "더", "도", "를", "을", "에", "의", "가", "는", "은", "로",
        "으로", "와", "과", "이런", "저런", "있는", "없는", "하는",
        "정도", "때문", "같은", "있어", "없어", "아주", "매우", "너무",
        "좀", "한", "된", "되는", "같아요", "것같아요", "합니다", "합니다",
    }

    all_text = " ".join(reviews_text)
    words = re.findall(r"[\uac00-\ud7a3]{2,}", all_text)
    words = [w for w in words if w not in stopwords and len(w) >= 2]
    counter = Counter(words)
    return counter.most_common(top_n)


# ─── Session State ───
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "selected_product" not in st.session_state:
    st.session_state.selected_product = None
if "reviews_input" not in st.session_state:
    st.session_state.reviews_input = ""
if "generated_reviews" not in st.session_state:
    st.session_state.generated_reviews = []


# ─── UI: Step 1 - 상품 검색 ───
st.subheader("1단계: 상품 검색")

col_search, col_btn = st.columns([4, 1])
with col_search:
    query = st.text_input(
        "상품명을 입력하세요",
        placeholder="예: 선크림, 토너, 클렌징폼...",
        key="search_query",
    )
with col_btn:
    st.write("")  # spacing
    search_clicked = st.button("🔍 검색", use_container_width=True)

if search_clicked and query:
    with st.spinner("올리브영에서 상품을 검색 중입니다..."):
        results = search_oliveyoung(query)
        if results:
            # 유사도 점수 계산 및 정렬
            for p in results:
                p["similarity"] = calculate_similarity(query, p["name"])
            results.sort(key=lambda x: x["similarity"], reverse=True)
            st.session_state.search_results = results
            st.session_state.selected_product = None
            st.session_state.generated_reviews = []
        else:
            st.warning("검색 결과가 없습니다. 다른 키워드로 시도해보세요.")

# ─── UI: 검색 결과 표시 ───
if st.session_state.search_results:
    st.divider()
    st.subheader("2단계: 상품 선택")
    st.info(f"총 {len(st.session_state.search_results)}개 상품이 검색되었습니다. 리뷰를 가져올 상품을 선택하세요.")

    for i, product in enumerate(st.session_state.search_results):
        with st.container(border=True):
            col_img, col_info, col_action = st.columns([1, 3, 1])

            with col_img:
                st.image(product["image"], width=100)

            with col_info:
                st.markdown(f"**{product['name'][:80]}**")
                st.caption(
                    f"🏷️ {product['brand']}  |  "
                    f"💰 {product['price']:,}원  |  "
                    f"⭐ {product['rating']}/10  |  "
                    f"💬 리뷰 {product['review_count']:,}개  |  "
                    f"🎯 유사도 {product['similarity']}%"
                )

            with col_action:
                st.write("")  # spacing
                if st.button("선택", key=f"select_{i}", use_container_width=True):
                    st.session_state.selected_product = product
                    st.session_state.generated_reviews = []

# ─── UI: Step 3 - 리뷰 입력 ───
if st.session_state.selected_product:
    product = st.session_state.selected_product
    st.divider()
    st.subheader("3단계: 리뷰 수집")

    with st.container(border=True):
        st.success(f"선택된 상품: **{product['name'][:80]}**")
        st.markdown(
            f"[올리브영에서 리뷰 보기]({PRODUCT_URL}{product['goods_no']})"
        )

    st.markdown("""
    #### 리뷰 입력 방법
    아래 링크에서 올리브영 상품 페이지를 열고, 리뷰 탭에서 **리뷰 텍스트를 복사**하여 아래에 붙여넣어 주세요.
    - 리뷰 하나당 **한 줄씩** 입력해주세요
    - 최소 **5개 이상**의 리뷰를 입력하면 더 자연스러운 결과를 얻을 수 있습니다
    """)

    reviews_text = st.text_area(
        "리뷰를 붙여넣어 주세요 (한 줄에 리뷰 하나)",
        height=300,
        placeholder=(
            "피부에 잘 맞고 발림성이 좋아요. 향도 은은해서 좋습니다.\n"
            "촉촉하고 끈적이지 않아서 여름에도 사용하기 좋아요.\n"
            "재구매 의사 있어요! 가격 대비 효과가 좋습니다.\n"
            "..."
        ),
        key="review_input_area",
    )

    # ─── UI: Step 4 - 리뷰 생성 ───
    if reviews_text.strip():
        reviews_list = [
            line.strip()
            for line in reviews_text.strip().split("\n")
            if len(line.strip()) > 5
        ]

        st.divider()
        st.subheader("4단계: 리뷰 생성")

        col_count, col_gen = st.columns([2, 2])
        with col_count:
            review_count = st.slider("생성할 리뷰 수", 1, 10, 3)
        with col_gen:
            st.write("")  # spacing
            generate_clicked = st.button(
                "✨ 리뷰 생성하기", use_container_width=True, type="primary"
            )

        if generate_clicked:
            if len(reviews_list) < 3:
                st.warning("최소 3개 이상의 리뷰를 입력해주세요.")
            else:
                with st.spinner("리뷰를 조합하여 새로운 리뷰를 생성 중..."):
                    generated = generate_reviews(reviews_list, review_count)
                    st.session_state.generated_reviews = generated

        # ─── 생성된 리뷰 출력 ───
        if st.session_state.generated_reviews:
            st.divider()
            st.subheader("생성된 리뷰")

            for i, review in enumerate(st.session_state.generated_reviews):
                with st.container(border=True):
                    st.markdown(f"**리뷰 #{i + 1}**")
                    st.write(review)

            # 키워드 분석
            st.divider()
            st.subheader("리뷰 키워드 분석")
            keywords = extract_keywords(reviews_list)
            if keywords:
                keyword_str = "  ".join(
                    [f"`{word}` ({count})" for word, count in keywords]
                )
                st.markdown(keyword_str)

            # 재생성 버튼
            if st.button("🔄 다시 생성하기"):
                generated = generate_reviews(
                    reviews_list, len(st.session_state.generated_reviews)
                )
                st.session_state.generated_reviews = generated
                st.rerun()
