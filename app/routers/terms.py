from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from app.db import get_conn
from app.deps import require_login
from app.templates_env import templates

router = APIRouter()


@router.get("")
def terms_list(request: Request, user: dict = Depends(require_login)):
    with get_conn() as conn:
        terms = conn.execute(
            'SELECT * FROM "TERM" WHERE is_deleted = FALSE ORDER BY term'
        ).fetchall()

    return templates.TemplateResponse(
        request,
        "terms/list.html",
        {"user": user, "active_nav": "terms", "terms": terms},
    )


@router.post("")
def terms_create(
    request: Request,
    term: str = Form(...),
    definition: str = Form(...),
    context: str = Form(None),
    category: str = Form(None),
    user: dict = Depends(require_login),
):
    with get_conn() as conn:
        conn.execute(
            '''
            INSERT INTO "TERM" (term, definition, context, category, created_by)
            VALUES (%s, %s, %s, %s, %s)
            ''',
            (term, definition, context, category, user["auth_id"]),
        )
    return RedirectResponse("/terms", status_code=303)


def _fetch_term(conn, term_id: int):
    row = conn.execute(
        'SELECT * FROM "TERM" WHERE term_id = %s AND is_deleted = FALSE', (term_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="용어를 찾을 수 없습니다.")
    return row


@router.get("/{term_id}")
def term_row_view(term_id: int, request: Request, user: dict = Depends(require_login)):
    with get_conn() as conn:
        t = _fetch_term(conn, term_id)
    return templates.TemplateResponse(request, "partials/term_row.html", {"t": t})


@router.get("/{term_id}/edit")
def term_row_edit(term_id: int, request: Request, user: dict = Depends(require_login)):
    with get_conn() as conn:
        t = _fetch_term(conn, term_id)
    return templates.TemplateResponse(request, "partials/term_row_edit.html", {"t": t})


@router.post("/{term_id}")
def term_update(
    term_id: int,
    request: Request,
    term: str = Form(...),
    definition: str = Form(...),
    context: str = Form(None),
    category: str = Form(None),
    user: dict = Depends(require_login),
):
    with get_conn() as conn:
        row = conn.execute(
            '''
            UPDATE "TERM"
            SET term = %s, definition = %s, context = %s, category = %s,
                updated_by = %s, updated_at = now()
            WHERE term_id = %s AND is_deleted = FALSE
            RETURNING *
            ''',
            (term, definition, context, category, user["auth_id"], term_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="용어를 찾을 수 없습니다.")
    return templates.TemplateResponse(request, "partials/term_row.html", {"t": row})


@router.post("/{term_id}/delete")
def term_delete(term_id: int, user: dict = Depends(require_login)):
    # TERM은 스키마 설계상 실제 삭제 대신 is_deleted 숨김 처리 (docs/schema.md 참고).
    with get_conn() as conn:
        row = conn.execute(
            'UPDATE "TERM" SET is_deleted = TRUE WHERE term_id = %s AND is_deleted = FALSE RETURNING term_id',
            (term_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="용어를 찾을 수 없습니다.")
    return Response(content="", media_type="text/html")
