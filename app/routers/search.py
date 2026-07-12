from fastapi import APIRouter, Depends, Request

from app.deps import require_login
from app.search_render import build_result_table
from app.templates_env import templates
from core.rag.qa import RagError, answer_question

router = APIRouter()


@router.get("/search")
def search(request: Request, q: str | None = None, user: dict = Depends(require_login)):
    if not q:
        return templates.TemplateResponse(
            request,
            "search/results.html",
            {"user": user, "query": None, "answer": None, "sql": None, "error": None, "columns": [], "table_rows": []},
        )

    columns, table_rows = [], []
    try:
        result = answer_question(q)
        answer, sql, error = result["answer"], result["sql"], None
        columns, table_rows = build_result_table(result["rows"])
    except RagError as e:
        answer, sql, error = None, None, str(e)

    return templates.TemplateResponse(
        request,
        "search/results.html",
        {
            "user": user,
            "query": q,
            "answer": answer,
            "sql": sql,
            "error": error,
            "columns": columns,
            "table_rows": table_rows,
        },
    )
