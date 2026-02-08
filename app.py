import streamlit as st
from curl_cffi import requests as cffi_requests
import random
import re
import json
import time
from collections import Counter

st.set_page_config(page_title="올리브영 리뷰 생성기", layout="wide")
st.title("🧴 올리브영 리뷰 생성기")
st.caption("올리브영 상품 URL을 입력하면 리뷰를 자동 수집하여 새로운 리뷰를 생성합니다.")

# ─── Constants ───
REVIEW_API = "https://m.oliveyoung.co.kr/review/api/v2/reviews"
IMPERSONATE_BROWSERS = ["chrome120", "chrome124", "safari17_0"]


# ─── API Functions ───
def extract_goods_number(url_or_text):
    """URL 또는 텍스트에서 상품번호 추출"""
    patterns = [
        r"goodsNo=([A-Z0-9]+)",
        r"goodsNumber=([A-Z0-9]+)",
        r"/goods/([A-Z]\d{12,})",
        r"([A-Z]\d{12,})",
    ]
    for pat in patterns:
        match = re.search(pat, url_or_text)
        if match:
            return match.group(1)
    return None


def fetch_reviews(goods_number, pages=3, size=10, max_retries=3):
    """올리브영 리뷰 API에서 리뷰 자동 수집 (재시도 포함)"""
    all_reviews = []

    for attempt in range(max_retries):
        all_reviews = []
        browser = IMPERSONATE_BROWSERS[attempt % len(IMPERSONATE_BROWSERS)]
        success = False

        for page in range(1, pages + 1):
            try:
                resp = cffi_requests.post(
                    REVIEW_API,
                    json={"goodsNumber": goods_number, "page": page, "size": size},
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    impersonate=browser,
                    timeout=15,
                )
                if resp.status_code == 403:
                    st.warning(f"차단 감지, 브라우저 변경 후 재시도 중... ({attempt + 1}/{max_retries})")
                    break
                if resp.status_code != 200:
                    st.warning(f"API 응답 오류: {resp.status_code}")
                    break

                data = resp.json()
                api_status = data.get("status", "")
                if api_status != "SUCCESS":
                    st.warning(f"API 상태: {api_status} - {data.get('message', '')}")
                    break

                reviews = data.get("data") or []
                if not reviews:
                    break
                for r in reviews:
                    content = r.get("content", "").strip()
                    if content:
                        all_reviews.append({
                            "content": content,
                            "score": r.get("reviewScore", 0),
                            "nickname": r.get("profileDto", {}).get("memberNickname", ""),
                            "date": r.get("createdDateTime", ""),
                        })
                success = True
            except Exception as e:
                st.warning(f"요청 오류: {e}")
                break

        if success and all_reviews:
            return all_reviews

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)

    return all_reviews


# ─── Review Generation ───
def split_sentences(text):
    """텍스트를 문장 단위로 분리"""
    sentences = re.split(r"(?<=[.!?~])\s+|(?<=다)\s+|(?<=요)\s+|(?<=음)\s+|\n+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 5]


def categorize_sentences(sentences):
    """문장을 카테고리별로 분류"""
    categories = {
        "purchase": [],
        "texture": [],
        "effect": [],
        "scent": [],
        "general": [],
        "recommend": [],
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

        for cat in category_order:
            cat_sents = categories[cat]
            if cat_sents and random.random() > 0.3:
                sent = random.choice(cat_sents)
                if sent not in parts:
                    parts.append(sent)

        while len(parts) < 3:
            sent = random.choice(all_sentences)
            if sent not in parts:
                parts.append(sent)

        if len(parts) > 6:
            parts = parts[:6]

        review_text = " ".join(parts)
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
        "좀", "한", "된", "되는", "같아요", "것같아요", "합니다",
    }

    all_text = " ".join(reviews_text)
    words = re.findall(r"[\uac00-\ud7a3]{2,}", all_text)
    words = [w for w in words if w not in stopwords and len(w) >= 2]
    counter = Counter(words)
    return counter.most_common(top_n)


# ─── Session State ───
if "fetched_reviews" not in st.session_state:
    st.session_state.fetched_reviews = []
if "generated_reviews" not in st.session_state:
    st.session_state.generated_reviews = []
if "goods_number" not in st.session_state:
    st.session_state.goods_number = None


# ─── UI: Step 1 - URL 입력 ───
st.subheader("1단계: 올리브영 상품 URL 입력")

product_url = st.text_input(
    "상품 URL을 붙여넣어 주세요",
    placeholder="https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000243621",
)

col_pages, col_btn = st.columns([2, 2])
with col_pages:
    max_pages = st.slider("수집할 리뷰 페이지 수", 1, 10, 3, help="페이지당 10개 리뷰")
with col_btn:
    st.write("")
    fetch_clicked = st.button("📥 리뷰 자동 수집", use_container_width=True, type="primary")

if fetch_clicked and product_url:
    goods_number = extract_goods_number(product_url)
    if not goods_number:
        st.error("올리브영 상품 URL에서 상품번호를 찾을 수 없습니다.")
    else:
        st.session_state.goods_number = goods_number
        with st.spinner(f"상품 {goods_number}의 리뷰를 수집 중..."):
            reviews = fetch_reviews(goods_number, pages=max_pages)
            if reviews:
                st.session_state.fetched_reviews = reviews
                st.session_state.generated_reviews = []
                st.success(f"총 {len(reviews)}개 리뷰를 수집했습니다!")
            else:
                st.warning("리뷰를 가져올 수 없습니다. URL을 확인해주세요.")

# ─── UI: Step 2 - 수집된 리뷰 확인 ───
if st.session_state.fetched_reviews:
    st.divider()
    st.subheader(f"2단계: 수집된 리뷰 ({len(st.session_state.fetched_reviews)}개)")

    with st.expander("수집된 리뷰 보기", expanded=False):
        for i, r in enumerate(st.session_state.fetched_reviews):
            score_stars = "⭐" * r["score"]
            st.markdown(f"**{i+1}.** {score_stars} _{r['nickname']}_ ({r['date']})")
            st.caption(r["content"][:200])

    # ─── UI: Step 3 - 리뷰 생성 ───
    st.divider()
    st.subheader("3단계: 새 리뷰 생성")

    col_count, col_gen = st.columns([2, 2])
    with col_count:
        review_count = st.slider("생성할 리뷰 수", 1, 10, 3)
    with col_gen:
        st.write("")
        generate_clicked = st.button(
            "✨ 리뷰 생성하기", use_container_width=True
        )

    if generate_clicked:
        contents = [r["content"] for r in st.session_state.fetched_reviews]
        if len(contents) < 3:
            st.warning("수집된 리뷰가 부족합니다. 더 많은 페이지를 수집해주세요.")
        else:
            with st.spinner("리뷰를 조합하여 새로운 리뷰를 생성 중..."):
                generated = generate_reviews(contents, review_count)
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
        st.subheader("📊 리뷰 키워드 분석")
        contents = [r["content"] for r in st.session_state.fetched_reviews]
        keywords = extract_keywords(contents)
        if keywords:
            keyword_str = "  ".join(
                [f"`{word}` ({count})" for word, count in keywords]
            )
            st.markdown(keyword_str)

        # 재생성 버튼
        if st.button("🔄 다시 생성하기"):
            contents = [r["content"] for r in st.session_state.fetched_reviews]
            generated = generate_reviews(
                contents, len(st.session_state.generated_reviews)
            )
            st.session_state.generated_reviews = generated
            st.rerun()
