from fastapi import APIRouter, Depends, Request

from app.deps import require_login
from app.templates_env import templates

router = APIRouter()

# 2026-07-12 잠금: 법 조문/종합보고서 같은 근거 문서 없이 모델이 "왜" 질문에
# 답을 지어낼 위험이 커서 중단. docs/design-decisions.md "자연어 검색 잠금" 참고.
# core.rag.qa를 아예 import하지 않아서 이 라우트에서 Ollama를 호출할 길이 없다.
LOCKED_MESSAGE = (
    "자연어 검색은 잠시 잠가뒀습니다. 법 조문·종합보고서 같은 근거 문서 없이 "
    "모델이 답을 지어낼 위험이 있어서, 근거 문서를 갖추기 전까지는 중단합니다. "
    "지금은 대시보드나 기관별 현황 화면에서 원문을 직접 확인해주세요."
)


@router.get("/search")
def search(request: Request, q: str | None = None, user: dict = Depends(require_login)):
    if not q:
        return templates.TemplateResponse(
            request,
            "search/results.html",
            {"user": user, "query": None, "answer": None, "sql": None, "error": None, "columns": [], "table_rows": []},
        )

    return templates.TemplateResponse(
        request,
        "search/results.html",
        {
            "user": user,
            "query": q,
            "answer": None,
            "sql": None,
            "error": LOCKED_MESSAGE,
            "columns": [],
            "table_rows": [],
        },
    )
