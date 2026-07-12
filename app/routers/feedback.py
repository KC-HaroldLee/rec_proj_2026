from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.db import get_conn
from app.deps import require_login

router = APIRouter()


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
