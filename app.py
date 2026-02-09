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


def fetch_reviews(goods_number, count=10, max_retries=3):
    """올리브영 리뷰 API에서 리뷰 자동 수집 (최신순, API 1회 호출)"""
    for attempt in range(max_retries):
        browser = IMPERSONATE_BROWSERS[attempt % len(IMPERSONATE_BROWSERS)]
        try:
            resp = cffi_requests.post(
                REVIEW_API,
                json={"goodsNumber": goods_number, "page": 1, "size": count},
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                impersonate=browser,
                timeout=15,
            )
            if resp.status_code == 403:
                st.warning(f"차단 감지, 재시도 중... ({attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)
                continue
            if resp.status_code != 200:
                st.warning(f"API 응답 오류: {resp.status_code}")
                return []

            data = resp.json()
            if data.get("status") != "SUCCESS":
                st.warning(f"API 상태: {data.get('status')} - {data.get('message', '')}")
                return []

            result = []
            for r in data.get("data") or []:
                content = r.get("content", "").strip()
                if content:
                    result.append({
                        "content": content,
                        "score": r.get("reviewScore", 0),
                        "nickname": r.get("profileDto", {}).get("memberNickname", ""),
                        "date": r.get("createdDateTime", ""),
                    })
            return result
        except Exception as e:
            st.warning(f"요청 오류: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return []


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
if "generated_positive" not in st.session_state:
    st.session_state.generated_positive = []
if "generated_negative" not in st.session_state:
    st.session_state.generated_negative = []


# ─── UI: Step 1 - URL 입력 ───
st.subheader("1단계: 올리브영 상품 URL 입력")

product_url = st.text_input(
    "상품 URL을 붙여넣어 주세요",
    placeholder="https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000243621",
)

col_count, col_btn = st.columns([2, 2])
with col_count:
    review_limit = st.slider("수집할 리뷰 수", 10, 30, 10, step=10, help="최신순으로 가져옵니다")
with col_btn:
    st.write("")
    fetch_clicked = st.button("📥 리뷰 자동 수집", use_container_width=True, type="primary")

if fetch_clicked and product_url:
    goods_number = extract_goods_number(product_url)
    if not goods_number:
        st.error("올리브영 상품 URL에서 상품번호를 찾을 수 없습니다.")
    else:
        with st.spinner(f"상품 {goods_number}의 리뷰를 수집 중... (최신순)"):
            reviews = fetch_reviews(goods_number, count=review_limit)
            if reviews:
                # 날짜 최신순 정렬
                reviews.sort(key=lambda x: x["date"], reverse=True)
                st.session_state.fetched_reviews = reviews
                st.session_state.generated_positive = []
                st.session_state.generated_negative = []

                # 별점별 통계
                positive = [r for r in reviews if r["score"] == 5]
                negative = [r for r in reviews if r["score"] == 1]
                st.success(
                    f"총 {len(reviews)}개 리뷰 수집 완료! "
                    f"(⭐5점: {len(positive)}개 | ⭐1점: {len(negative)}개)"
                )
            else:
                st.warning("리뷰를 가져올 수 없습니다. URL을 확인해주세요.")

# ─── UI: Step 2 - 수집된 리뷰 확인 (5점/1점 분리) ───
if st.session_state.fetched_reviews:
    reviews = st.session_state.fetched_reviews
    positive = [r for r in reviews if r["score"] == 5]
    negative = [r for r in reviews if r["score"] == 1]

    st.divider()
    st.subheader("2단계: 수집된 리뷰 확인")

    tab_pos, tab_neg, tab_all = st.tabs([
        f"⭐ 5점 리뷰 ({len(positive)}개)",
        f"💀 1점 리뷰 ({len(negative)}개)",
        f"📋 전체 리뷰 ({len(reviews)}개)",
    ])

    with tab_pos:
        if positive:
            for i, r in enumerate(positive):
                st.markdown(f"**{i+1}.** ⭐⭐⭐⭐⭐ _{r['nickname']}_ ({r['date']})")
                st.caption(r["content"][:300])
        else:
            st.info("5점 리뷰가 없습니다. 페이지 수를 늘려서 다시 수집해보세요.")

    with tab_neg:
        if negative:
            for i, r in enumerate(negative):
                st.markdown(f"**{i+1}.** ⭐ _{r['nickname']}_ ({r['date']})")
                st.caption(r["content"][:300])
        else:
            st.info("1점 리뷰가 없습니다. 페이지 수를 늘려서 다시 수집해보세요.")

    with tab_all:
        for i, r in enumerate(reviews):
            stars = "⭐" * r["score"]
            st.markdown(f"**{i+1}.** {stars} _{r['nickname']}_ ({r['date']})")
            st.caption(r["content"][:300])

    # ─── UI: Step 3 - 리뷰 생성 (5점/1점 각각) ───
    st.divider()
    st.subheader("3단계: 새 리뷰 생성")

    col_count, col_gen = st.columns([2, 2])
    with col_count:
        review_count = st.slider("별점별 생성할 리뷰 수", 1, 10, 3)
    with col_gen:
        st.write("")
        generate_clicked = st.button(
            "✨ 리뷰 생성하기", use_container_width=True, type="primary"
        )

    if generate_clicked:
        pos_contents = [r["content"] for r in positive]
        neg_contents = [r["content"] for r in negative]

        gen_pos = []
        gen_neg = []

        if len(pos_contents) >= 3:
            gen_pos = generate_reviews(pos_contents, review_count)
        if len(neg_contents) >= 3:
            gen_neg = generate_reviews(neg_contents, review_count)

        if not gen_pos and not gen_neg:
            st.warning("5점 또는 1점 리뷰가 각각 3개 이상 필요합니다. 페이지 수를 늘려서 다시 수집해주세요.")
        else:
            st.session_state.generated_positive = gen_pos
            st.session_state.generated_negative = gen_neg

    # ─── 생성된 리뷰 출력 (탭 분리) ───
    if st.session_state.generated_positive or st.session_state.generated_negative:
        st.divider()
        st.subheader("생성된 리뷰")

        gen_tab_pos, gen_tab_neg = st.tabs([
            f"⭐ 5점 기반 생성 ({len(st.session_state.generated_positive)}개)",
            f"💀 1점 기반 생성 ({len(st.session_state.generated_negative)}개)",
        ])

        with gen_tab_pos:
            if st.session_state.generated_positive:
                for i, review in enumerate(st.session_state.generated_positive):
                    with st.container(border=True):
                        st.markdown(f"**긍정 리뷰 #{i + 1}**")
                        st.write(review)
            else:
                st.info("5점 리뷰가 부족하여 생성하지 못했습니다.")

        with gen_tab_neg:
            if st.session_state.generated_negative:
                for i, review in enumerate(st.session_state.generated_negative):
                    with st.container(border=True):
                        st.markdown(f"**부정 리뷰 #{i + 1}**")
                        st.write(review)
            else:
                st.info("1점 리뷰가 부족하여 생성하지 못했습니다.")

        # 키워드 분석 (5점 vs 1점)
        st.divider()
        st.subheader("📊 키워드 비교 분석")

        kw_col_pos, kw_col_neg = st.columns(2)

        with kw_col_pos:
            st.markdown("**⭐ 5점 리뷰 키워드**")
            pos_contents = [r["content"] for r in positive]
            if pos_contents:
                kw = extract_keywords(pos_contents)
                if kw:
                    st.markdown("  ".join([f"`{w}` ({c})" for w, c in kw]))
            else:
                st.caption("데이터 없음")

        with kw_col_neg:
            st.markdown("**💀 1점 리뷰 키워드**")
            neg_contents = [r["content"] for r in negative]
            if neg_contents:
                kw = extract_keywords(neg_contents)
                if kw:
                    st.markdown("  ".join([f"`{w}` ({c})" for w, c in kw]))
            else:
                st.caption("데이터 없음")

        # 재생성 버튼
        if st.button("🔄 다시 생성하기"):
            pos_contents = [r["content"] for r in positive]
            neg_contents = [r["content"] for r in negative]
            if len(pos_contents) >= 3:
                st.session_state.generated_positive = generate_reviews(pos_contents, review_count)
            if len(neg_contents) >= 3:
                st.session_state.generated_negative = generate_reviews(neg_contents, review_count)
            st.rerun()
