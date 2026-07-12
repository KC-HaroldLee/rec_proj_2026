from fastapi import APIRouter, Depends, HTTPException, Request

from app.categories import category_sort_key, resolve_category
from app.db import get_conn
from app.deps import require_login
from app.markdown_render import render_markdown
from app.stuck import classify_year
from app.templates_env import templates

router = APIRouter()


@router.get("")
def recs_list(request: Request, category: str | None = None, user: dict = Depends(require_login)):
    selected_category, filter_category = resolve_category(category)

    with get_conn() as conn:
        categories = sorted(
            (r["category"] for r in conn.execute('SELECT DISTINCT category FROM "REC"').fetchall()),
            key=category_sort_key,
        )
        # rec_no는 "2-10" 같은 문자열이라 그냥 ORDER BY하면 "2-1" 다음에 "2-10"이
        # 오는 사전식 정렬이 된다. "-" 앞뒤를 숫자로 쪼개서 진짜 순서대로 정렬.
        recs = conn.execute(
            '''
            SELECT rec_id, rec_no, category, content FROM "REC"
            WHERE %(cat)s::text IS NULL OR category = %(cat)s::text
            ORDER BY category, split_part(rec_no, '-', 1)::int, split_part(rec_no, '-', 2)::int
            ''',
            {"cat": filter_category},
        ).fetchall()

    return templates.TemplateResponse(
        request,
        "recs/list.html",
        {
            "user": user,
            "active_nav": "recs",
            "recs": recs,
            "categories": categories,
            "selected_category": selected_category,
        },
    )


@router.get("/{rec_id}")
def rec_detail(rec_id: int, request: Request, user: dict = Depends(require_login)):
    with get_conn() as conn:
        rec = conn.execute('SELECT * FROM "REC" WHERE rec_id = %s', (rec_id,)).fetchone()
        if not rec:
            raise HTTPException(status_code=404, detail="권고를 찾을 수 없습니다.")

        # REC_INST(권고+기관) 단위로 LEFT JOIN IMPL: 아직 이행보고가 안 들어온
        # link_id도 institutions 목록에는 나오게 하려고 LEFT JOIN을 쓴다.
        # exact_same/similarity: 대시보드와 같은 LAG 방식으로 "바로 전 연도 대비"
        # 객관적 신호를 계산해서, status(기관이 스스로 쓴 자기보고)와 나란히 보여준다
        # — "정부는 이렇게 주장하지만 텍스트는 그대로다" 대비를 상세페이지에서도 드러내려는 것.
        impl_rows = conn.execute(
            '''
            SELECT ri.link_id, i.inst_id, i.name AS inst_name,
                   sub.impl_id, sub.year, sub.status, sub.plan, sub.source,
                   sub.exact_same, sub.similarity
            FROM "REC_INST" ri
            JOIN "INST" i ON ri.inst_id = i.inst_id
            LEFT JOIN (
                SELECT im.link_id, im.impl_id, im.year, im.status, im.plan, im.source,
                       (im.status = LAG(im.status) OVER w) AS exact_same,
                       CASE WHEN im.embedding IS NOT NULL AND LAG(im.embedding) OVER w IS NOT NULL
                            THEN 1 - (im.embedding <=> LAG(im.embedding) OVER w) END AS similarity
                FROM "IMPL" im
                WINDOW w AS (PARTITION BY im.link_id ORDER BY im.year)
            ) sub ON sub.link_id = ri.link_id
            WHERE ri.rec_id = %s
            ORDER BY i.name, sub.year
            ''',
            (rec_id,),
        ).fetchall()

        impl_ids = [r["impl_id"] for r in impl_rows if r["impl_id"] is not None]
        feedback_rows = []
        if impl_ids:
            feedback_rows = conn.execute(
                '''
                SELECT f.feedback_id, f.auth_id, f.impl_id, f.content, f.evidence_url, f.created_at, a.auth_name
                FROM "FEEDBACK" f
                JOIN "AUTH" a ON f.auth_id = a.auth_id
                WHERE f.impl_id = ANY(%s)
                ORDER BY f.created_at
                ''',
                (impl_ids,),
            ).fetchall()

        evidences = conn.execute(
            '''
            SELECT e.evid_id, e.code, e.title
            FROM "EVID" e
            JOIN "REC_EVID" re ON e.evid_id = re.evid_id
            WHERE re.rec_id = %s
            ''',
            (rec_id,),
        ).fetchall()

    feedback_by_impl: dict[int, list] = {}
    for f in feedback_rows:
        feedback_by_impl.setdefault(f["impl_id"], []).append(f)

    institutions: dict[int, dict] = {}
    for row in impl_rows:
        inst = institutions.setdefault(
            row["inst_id"], {"inst_id": row["inst_id"], "name": row["inst_name"], "years": []}
        )
        if row["impl_id"] is not None:
            is_first_report = len(inst["years"]) == 0
            badge, badge_label = classify_year(row["exact_same"], row["similarity"], is_first_report)
            inst["years"].append(
                {
                    "impl_id": row["impl_id"],
                    "year": row["year"],
                    "status_html": render_markdown(row["status"]),
                    "plan_html": render_markdown(row["plan"]),
                    "source": row["source"],
                    "feedback": feedback_by_impl.get(row["impl_id"], []),
                    "badge": badge,
                    "badge_label": badge_label,
                }
            )

    return templates.TemplateResponse(
        request,
        "recs/detail.html",
        {
            "user": user,
            "active_nav": "recs",
            "rec": rec,
            "content_html": render_markdown(rec["content"]),
            "necessity_html": render_markdown(rec["necessity"]),
            "institutions": list(institutions.values()),
            "evidences": evidences,
        },
    )
