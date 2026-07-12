"""docs/design-decisions.md의 "정체(복붙) 탐지" 완전일치 기준 계산.
dashboard.py, institutions.py가 공유해서 쓴다.

"이행률"이라고 부르지 않는다 — status 텍스트가 바뀌었는지는 셀 수 있어도,
그 변화가 실질적 이행완료인지는 시스템이 판단할 수 없다(docs/design-decisions.md 참고).
"""


def compute_streak(years: list[dict]) -> int | None:
    """최근 연도부터 거슬러올라가며 status가 몇 년 연속 동일한지.
    비교할 연도가 2개 미만이면 판단 불가(None)를 반환한다."""
    if len(years) < 2:
        return None
    streak = 1
    for i in range(len(years) - 1, 0, -1):
        if years[i]["status"] == years[i - 1]["status"]:
            streak += 1
        else:
            break
    return streak


def mark_same_as_prev(years: list[dict]) -> None:
    """year-dot 렌더링용: 각 연도 dict에 same_as_prev 불리언을 in-place로 채운다."""
    prev_status = None
    for y in years:
        y["same_as_prev"] = prev_status is not None and y["status"] == prev_status
        prev_status = y["status"]


# scripts/test_embedding_similarity.py 실측: 표현만 다른 근사-재탕 쌍의 코사인 유사도
# 0.9501, 명백히 다른 내용(네거티브 컨트롤)은 0.8462. 그 사이 어딘가에서 보수적으로
# 잡았다 — 실제 데이터가 더 쌓이면 조정 필요 (core/similarity/schema.sql 참고).
SUSPECT_SIMILARITY_THRESHOLD = 0.93


def trailing_streak(flags: list[bool | None]) -> int:
    """flags[i]가 True면 그 연도가 바로 전 연도와 '같다'는 뜻(완전일치든 유사도든).
    가장 최근 항목부터 거슬러 올라가며 연속 True 개수 + 1을 반환한다.
    flags가 비어있으면(비교 불가) 0."""
    if not flags:
        return 0
    streak = 1
    for flag in reversed(flags):
        if flag:
            streak += 1
        else:
            break
    return streak


# "신호등" 배지 종류 — dashboard.py, recs.py, institutions.py가 전부 이 4가지만 쓴다.
# 🔴 stuck(완전 동일) / 🟡 suspect(유사, 의심) / 🟢 progress(다름, 변화 있음) /
# ⚪ watch(비교 불가 — status가 비어있거나 등등). 첫 보고(비교 대상 자체가 없음)는 배지 없음(None).
def classify_year(exact_same: bool | None, similarity: float | None, is_first_report: bool) -> tuple[str | None, str | None]:
    """LAG로 계산한 exact_same/similarity 한 쌍을 (badge, badge_label)로 변환.

    exact_same이 None인 건 "전년도와 비교했는데 알 수 없음"(SQL NULL = 두 status 중
    하나 이상이 NULL) 또는 "애초에 전년도가 없음"(진짜 첫 보고) 둘 다일 수 있어서,
    호출부가 is_first_report로 구분해줘야 한다.
    """
    if exact_same:
        return "stuck", "전년도와 완전 동일"
    if similarity is not None and similarity >= SUSPECT_SIMILARITY_THRESHOLD:
        return "suspect", f"전년도와 유사 (의심, 유사도 {similarity:.0%})"
    if exact_same is not None:  # 비교 대상(전년도)이 있었는데 다름 = 진짜 변화
        return "progress", "전년도와 다름"
    if is_first_report:
        return None, None
    return "watch", "이행현황 미기재로 비교 불가"
