from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from app.db import get_conn
from app.deps import require_login
from app.templates_env import templates

router = APIRouter()

_FEEDBACK_BY_ID = '''
    SELECT f.feedback_id, f.auth_id, f.content, f.evidence_url, f.created_at,
           a.auth_name, r.rec_no, i.name AS inst_name
    FROM "FEEDBACK" f
    JOIN "AUTH" a ON f.auth_id = a.auth_id
    JOIN "IMPL" im ON f.impl_id = im.impl_id
    JOIN "REC_INST" ri ON im.link_id = ri.link_id
    JOIN "REC" r ON ri.rec_id = r.rec_id
    JOIN "INST" i ON ri.inst_id = i.inst_id
    WHERE f.feedback_id = %s
'''


def _fetch_feedback(conn, feedback_id: int):
    row = conn.execute(_FEEDBACK_BY_ID, (feedback_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="피드백을 찾을 수 없습니다.")
    return row


def _require_owner(row, user: dict):
    # 본인이 작성한 피드백만 수정/삭제 가능 — TERM(용어사전)과 달리 작성자 제한을 둔다.
    if row["auth_id"] != user["auth_id"]:
        raise HTTPException(status_code=403, detail="본인이 작성한 피드백만 수정/삭제할 수 있습니다.")


@router.get("/feedback")
def feedback_list(request: Request, user: dict = Depends(require_login)):
    with get_conn() as conn:
        recent_feedback = conn.execute(
            '''
            SELECT f.feedback_id, f.auth_id, f.content, f.evidence_url, f.created_at,
                   a.auth_name, r.rec_no, i.name AS inst_name
            FROM "FEEDBACK" f
            JOIN "AUTH" a ON f.auth_id = a.auth_id
            JOIN "IMPL" im ON f.impl_id = im.impl_id
            JOIN "REC_INST" ri ON im.link_id = ri.link_id
            JOIN "REC" r ON ri.rec_id = r.rec_id
            JOIN "INST" i ON ri.inst_id = i.inst_id
            ORDER BY f.created_at DESC
            '''
        ).fetchall()

    return templates.TemplateResponse(
        request,
        "feedback/list.html",
        {"user": user, "recent_feedback": recent_feedback, "ctx": "feed"},
    )


@router.post("/impl/{impl_id}/feedback")
def create_feedback(
    impl_id: int,
    request: Request,
    content: str = Form(...),
    evidence_url: str = Form(None),
    user: dict = Depends(require_login),
):
    with get_conn() as conn:
        rec = conn.execute(
            '''
            SELECT ri.rec_id
            FROM "IMPL" im
            JOIN "REC_INST" ri ON im.link_id = ri.link_id
            WHERE im.impl_id = %s
            ''',
            (impl_id,),
        ).fetchone()
        if not rec:
            raise HTTPException(status_code=404, detail="이행보고를 찾을 수 없습니다.")

        conn.execute(
            '''
            INSERT INTO "FEEDBACK" (impl_id, auth_id, content, evidence_url)
            VALUES (%s, %s, %s, %s)
            ''',
            (impl_id, user["auth_id"], content, evidence_url),
        )

    return RedirectResponse(f"/recs/{rec['rec_id']}#impl-{impl_id}", status_code=303)


@router.get("/feedback/{feedback_id}")
def feedback_item_view(
    feedback_id: int, request: Request, ctx: str | None = None, user: dict = Depends(require_login)
):
    with get_conn() as conn:
        row = _fetch_feedback(conn, feedback_id)
    return templates.TemplateResponse(request, "partials/feedback_item.html", {"f": row, "user": user, "ctx": ctx})


@router.get("/feedback/{feedback_id}/edit")
def feedback_item_edit(
    feedback_id: int, request: Request, ctx: str | None = None, user: dict = Depends(require_login)
):
    with get_conn() as conn:
        row = _fetch_feedback(conn, feedback_id)
    _require_owner(row, user)
    return templates.TemplateResponse(request, "partials/feedback_item_edit.html", {"f": row, "ctx": ctx})


@router.post("/feedback/{feedback_id}")
def feedback_update(
    feedback_id: int,
    request: Request,
    content: str = Form(...),
    evidence_url: str = Form(None),
    ctx: str | None = None,
    user: dict = Depends(require_login),
):
    with get_conn() as conn:
        row = _fetch_feedback(conn, feedback_id)
        _require_owner(row, user)
        conn.execute(
            'UPDATE "FEEDBACK" SET content = %s, evidence_url = %s WHERE feedback_id = %s',
            (content, evidence_url, feedback_id),
        )
        row = _fetch_feedback(conn, feedback_id)
    return templates.TemplateResponse(request, "partials/feedback_item.html", {"f": row, "user": user, "ctx": ctx})


@router.post("/feedback/{feedback_id}/delete")
def feedback_delete(feedback_id: int, user: dict = Depends(require_login)):
    with get_conn() as conn:
        row = _fetch_feedback(conn, feedback_id)
        _require_owner(row, user)
        conn.execute('DELETE FROM "FEEDBACK" WHERE feedback_id = %s', (feedback_id,))
    return Response(content="", media_type="text/html")
