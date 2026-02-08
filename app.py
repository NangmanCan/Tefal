import streamlit as st
import random
import re
from collections import Counter

st.set_page_config(page_title="올리브영 리뷰 생성기", layout="wide")
st.title("🧴 올리브영 리뷰 생성기")
st.caption("올리브영 상품 리뷰를 조합하여 새로운 리뷰를 만들어드립니다.")


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

        # 각 카테고리에서 랜덤으로 문장 선택
        for cat in category_order:
            cat_sents = categories[cat]
            if cat_sents and random.random() > 0.3:  # 70% 확률로 카테고리 포함
                sent = random.choice(cat_sents)
                if sent not in parts:
                    parts.append(sent)

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
        "좀", "한", "된", "되는", "같아요", "것같아요", "합니다",
    }

    all_text = " ".join(reviews_text)
    words = re.findall(r"[\uac00-\ud7a3]{2,}", all_text)
    words = [w for w in words if w not in stopwords and len(w) >= 2]
    counter = Counter(words)
    return counter.most_common(top_n)


# ─── Session State ───
if "generated_reviews" not in st.session_state:
    st.session_state.generated_reviews = []


# ─── UI: Step 1 - 상품 정보 입력 ───
st.subheader("1단계: 상품 정보")

product_name = st.text_input(
    "상품명 (참고용)",
    placeholder="예: 아누아 어성초 토너",
)

product_url = st.text_input(
    "올리브영 상품 URL (선택사항)",
    placeholder="https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=...",
)

if product_url:
    st.markdown(f"[올리브영에서 리뷰 보기]({product_url})")

# ─── UI: Step 2 - 리뷰 입력 ───
st.divider()
st.subheader("2단계: 리뷰 입력")

st.markdown("""
올리브영 상품 페이지에서 **리뷰 텍스트를 복사**하여 아래에 붙여넣어 주세요.
- 리뷰 하나당 **한 줄씩** 입력
- 최소 **5개 이상** 입력하면 더 자연스러운 결과
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
)

# ─── UI: Step 3 - 리뷰 생성 ───
if reviews_text.strip():
    reviews_list = [
        line.strip()
        for line in reviews_text.strip().split("\n")
        if len(line.strip()) > 5
    ]

    st.divider()
    st.subheader("3단계: 리뷰 생성")

    col_count, col_gen = st.columns([2, 2])
    with col_count:
        review_count = st.slider("생성할 리뷰 수", 1, 10, 3)
    with col_gen:
        st.write("")
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
        st.subheader("📊 리뷰 키워드 분석")
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
