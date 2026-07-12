"""권고 category 필터 칩에서 공유하는 상수/헬퍼. dashboard.py, institutions.py 등에서 쓴다."""

ALL_CATEGORIES = "all"
DEFAULT_CATEGORY = "4·16세월호참사"


def resolve_category(category: str | None) -> tuple[str, str | None]:
    """쿼리파라미터 category를 (화면에 표시할 선택값, SQL WHERE에 쓸 필터값)으로 변환.

    쿼리파라미터가 아예 없으면(첫 방문) DEFAULT_CATEGORY를 고른 것으로 취급한다.
    필터값이 None이면 전체(필터 없음).
    """
    selected = category if category is not None else DEFAULT_CATEGORY
    filter_value = None if selected == ALL_CATEGORIES else selected
    return selected, filter_value
