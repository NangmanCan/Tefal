import streamlit as st
from curl_cffi import requests as cffi_requests
import re
import json
import time
import urllib.request
from collections import Counter

st.set_page_config(page_title="올리브영 리뷰 생성기", layout="wide")
st.title("🧴 올리브영 리뷰 생성기")
st.caption("올리브영 상품 URL을 입력하면 리뷰를 자동 수집하여 Gemini AI로 새로운 리뷰를 생성합니다.")

# ─── Constants ───
REVIEW_API = "https://m.oliveyoung.co.kr/review/api/v2/reviews"
IMPERSONATE_BROWSERS = ["chrome120", "chrome124", "safari17_0"]
GEMINI_API_KEY = "AIzaSyAHlHAWdekllJEEwITQ5xJnzdhLDeqjg8w"
GEMINI_MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]


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


# ─── Gemini AI Review Generation ───
def call_gemini(prompt):
    """Gemini API REST 호출 - 여러 모델 자동 시도"""
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": 2048,
        },
    }).encode("utf-8")

    last_error = None
    for model in GEMINI_MODELS:
        for api_ver in ["v1beta", "v1"]:
            url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model}:generateContent?key={GEMINI_API_KEY}"
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data["candidates"][0]["content"]["parts"][0]["text"]
            except urllib.error.HTTPError as e:
                last_error = f"{model} ({api_ver}): {e.code} - {e.read().decode('utf-8', errors='ignore')[:200]}"
                continue
            except Exception as e:
                last_error = f"{model} ({api_ver}): {e}"
                continue

    raise Exception(f"모든 모델 실패. 마지막 오류: {last_error}")


def generate_reviews_with_gemini(reviews_text, count=3, sentiment="positive"):
    """Gemini AI를 사용하여 리뷰 생성"""
    if len(reviews_text) < 1:
        return ["리뷰 데이터가 부족합니다."]

    reviews_sample = "\n".join([f"- {r}" for r in reviews_text[:15]])

    if sentiment == "positive":
        tone_desc = "긍정적이고 만족스러운 톤 (5점 리뷰)"
        instruction = "상품에 대해 만족하는 실제 구매자처럼 자연스러운 긍정 리뷰를 작성하세요."
    else:
        tone_desc = "부정적이고 불만족스러운 톤 (1점 리뷰)"
        instruction = "상품에 대해 불만족한 실제 구매자처럼 자연스러운 부정 리뷰를 작성하세요."

    prompt = f"""아래는 올리브영 화장품 상품의 실제 리뷰입니다.

[기존 리뷰]
{reviews_sample}

[요청]
위 리뷰들의 말투, 표현 방식, 언급하는 포인트를 참고하여 {tone_desc}의 새로운 리뷰 {count}개를 생성해주세요.

{instruction}

규칙:
- 각 리뷰는 2~4문장, 자연스러운 한국어 구어체로 작성
- 실제 올리브영 리뷰처럼 보이도록 작성 (이모티콘 가끔 사용 가능)
- 기존 리뷰를 그대로 복사하지 말고 새롭게 작성
- 각 리뷰를 번호로 구분 (1. 2. 3. ...)
- 번호와 리뷰 내용만 출력하고 다른 설명은 하지 마세요"""

    try:
        result = call_gemini(prompt)
        reviews = []
        for line in result.strip().split("\n"):
            line = line.strip()
            cleaned = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
            if cleaned and len(cleaned) > 10:
                reviews.append(cleaned)
        return reviews[:count] if reviews else ["리뷰 생성 결과를 파싱하지 못했습니다."]
    except Exception as e:
        return [f"Gemini API 오류: {e}"]


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

# ─── Sidebar: API 테스트 ───
with st.sidebar:
    st.markdown("### Gemini API 상태")
    if st.button("API 연결 테스트"):
        with st.spinner("테스트 중..."):
            try:
                result = call_gemini("안녕이라고만 답해줘")
                st.success(f"연결 성공! 응답: {result[:50]}")
            except Exception as e:
                st.error(f"실패: {e}")

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
    st.subheader("3단계: AI 리뷰 생성")

    col_count, col_gen = st.columns([2, 2])
    with col_count:
        review_count = st.slider("별점별 생성할 리뷰 수", 1, 10, 3)
    with col_gen:
        st.write("")
        generate_clicked = st.button(
            "✨ Gemini AI 리뷰 생성", use_container_width=True, type="primary"
        )

    if generate_clicked:
        pos_contents = [r["content"] for r in positive]
        neg_contents = [r["content"] for r in negative]

        gen_pos = []
        gen_neg = []

        if pos_contents:
            with st.spinner("Gemini AI로 긍정 리뷰 생성 중..."):
                gen_pos = generate_reviews_with_gemini(pos_contents, review_count, "positive")
        if neg_contents:
            with st.spinner("Gemini AI로 부정 리뷰 생성 중..."):
                gen_neg = generate_reviews_with_gemini(neg_contents, review_count, "negative")

        if not gen_pos and not gen_neg:
            st.warning("5점 또는 1점 리뷰가 최소 1개 이상 필요합니다.")
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
            if pos_contents:
                st.session_state.generated_positive = generate_reviews_with_gemini(
                    pos_contents, review_count, "positive"
                )
            if neg_contents:
                st.session_state.generated_negative = generate_reviews_with_gemini(
                    neg_contents, review_count, "negative"
                )
            st.rerun()
