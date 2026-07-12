"""권고 category 필터 칩에서 공유하는 상수/헬퍼. dashboard.py, institutions.py 등에서 쓴다."""

ALL_CATEGORIES = "all"
DEFAULT_CATEGORY = "4·16세월호참사"

# 화면에 카테고리를 나열할 때(필터 칩, 요약 라벨 등) 공통으로 쓰는 표시 순서.
# DB의 ORDER BY category(사전식)와는 다른, 사람이 보기 자연스러운 순서를 강제한다.
CATEGORY_ORDER = ["가습기살균제참사", "4·16세월호참사", "재난 및 피해지원 일반, 자료기록"]


def category_sort_key(category: str) -> tuple[int, str]:
    """CATEGORY_ORDER 기준 정렬 키. 목록에 없는 카테고리는 뒤로 밀리되 이름순으로 묶인다."""
    try:
        return (CATEGORY_ORDER.index(category), "")
    except ValueError:
        return (len(CATEGORY_ORDER), category)


def resolve_category(category: str | None) -> tuple[str, str | None]:
    """쿼리파라미터 category를 (화면에 표시할 선택값, SQL WHERE에 쓸 필터값)으로 변환.

    쿼리파라미터가 아예 없으면(첫 방문) DEFAULT_CATEGORY를 고른 것으로 취급한다.
    필터값이 None이면 전체(필터 없음).
    """
    selected = category if category is not None else DEFAULT_CATEGORY
    filter_value = None if selected == ALL_CATEGORIES else selected
    return selected, filter_value
