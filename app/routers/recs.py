from fastapi import APIRouter, Depends, HTTPException, Request

from app.categories import category_sort_key, resolve_category
from app.db import get_conn
from app.deps import require_login
from app.feedback_render import attach_feedback_extras
from app.markdown_render import render_markdown
from app.stuck import classify_year
from app.templates_env import templates

router = APIRouter()


@router.get("")
def recs_list(
    request: Request,
    category: str | None = None,
    inst_id: int | None = None,
    user: dict = Depends(require_login),
):
    selected_category, filter_category = resolve_category(category)

    with get_conn() as conn:
        categories = sorted(
            (r["category"] for r in conn.execute('SELECT DISTINCT category FROM "REC"').fetchall()),
            key=category_sort_key,
        )
        # 전체 기관 목록: 상단 필터 칩에 쓴다 (category 필터와 동일하게 쿼리파라미터로 조합).
        institutions = conn.execute('SELECT inst_id, name FROM "INST" ORDER BY inst_id').fetchall()

        # rec_no는 "2-10" 같은 문자열이라 그냥 ORDER BY하면 "2-1" 다음에 "2-10"이
        # 오는 사전식 정렬이 된다. "-" 앞뒤를 숫자로 쪼개서 진짜 순서대로 정렬.
        # inst_id가 있으면 그 기관이 담당하는 권고만 남긴다 (REC_INST에 존재하는지 EXISTS로 확인).
        recs = conn.execute(
            '''
            SELECT rec_id, rec_no, category, content FROM "REC" r
            WHERE (%(cat)s::text IS NULL OR category = %(cat)s::text)
              AND (%(inst_id)s::int IS NULL OR EXISTS (
                  SELECT 1 FROM "REC_INST" ri WHERE ri.rec_id = r.rec_id AND ri.inst_id = %(inst_id)s::int
              ))
            ORDER BY category, split_part(rec_no, '-', 1)::int, split_part(rec_no, '-', 2)::int
            ''',
            {"cat": filter_category, "inst_id": inst_id},
        ).fetchall()

        # 각 권고 행 아래에 "이 권고를 담당하는 기관" 버튼을 달아주기 위한 목록
        # (전체 기관 목록이 아니라, 그 권고와 REC_INST로 실제 연결된 기관만).
        rec_ids = [r["rec_id"] for r in recs]
        rec_inst_rows = (
            conn.execute(
                '''
                SELECT ri.rec_id, i.inst_id, i.name
                FROM "REC_INST" ri
                JOIN "INST" i ON ri.inst_id = i.inst_id
                WHERE ri.rec_id = ANY(%s)
                ORDER BY i.inst_id
                ''',
                (rec_ids,),
            ).fetchall()
            if rec_ids
            else []
        )

    rec_institutions: dict[int, list] = {}
    for row in rec_inst_rows:
        rec_institutions.setdefault(row["rec_id"], []).append({"inst_id": row["inst_id"], "name": row["name"]})
    for r in recs:
        r["institutions"] = rec_institutions.get(r["rec_id"], [])

    return templates.TemplateResponse(
        request,
        "recs/list.html",
        {
            "user": user,
            "active_nav": "recs",
            "recs": recs,
            "categories": categories,
            "selected_category": selected_category,
            "institutions": institutions,
            "selected_inst_id": inst_id,
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

        link_ids = list({r["link_id"] for r in impl_rows})
        feedback_rows = []
        if link_ids:
            # link_id로 한 번에 긁는다: impl_id가 있는 건 특정 연도 보고에 대한 피드백,
            # impl_id가 NULL인 건 "이행보고 자체가 없음"에 대한 피드백(아래 no_report 카드용).
            feedback_rows = conn.execute(
                '''
                SELECT f.feedback_id, f.auth_id, f.link_id, f.impl_id, f.content, f.created_at, a.auth_name
                FROM "FEEDBACK" f
                JOIN "AUTH" a ON f.auth_id = a.auth_id
                WHERE f.link_id = ANY(%s)
                ORDER BY f.created_at
                ''',
                (link_ids,),
            ).fetchall()
            attach_feedback_extras(conn, feedback_rows)

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
    feedback_by_link_only: dict[int, list] = {}
    for f in feedback_rows:
        if f["impl_id"] is not None:
            feedback_by_impl.setdefault(f["impl_id"], []).append(f)
        else:
            feedback_by_link_only.setdefault(f["link_id"], []).append(f)

    institutions: dict[int, dict] = {}
    for row in impl_rows:
        inst = institutions.setdefault(
            row["inst_id"],
            {"inst_id": row["inst_id"], "name": row["inst_name"], "link_id": row["link_id"], "years": []},
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

    # 이 기관이 이 권고에 대해 이행보고를 한 번도 안 냈으면(IMPL row 자체가 없으면),
    # IMPL에 가짜 row를 넣는 대신 화면에서만 "보고 없음" 카드 1개를 합성해 넣는다.
    # 그래야 뱃지/임베딩/대시보드가 참조하는 IMPL의 "실제 제출된 보고"라는 의미가
    # 안 깨지면서도, 피드백 UI(timeline-year 블록)는 그대로 재사용할 수 있다.
    for inst in institutions.values():
        if not inst["years"]:
            inst["years"].append(
                {
                    "impl_id": None,
                    "year": None,
                    "status_html": None,
                    "plan_html": None,
                    "source": None,
                    "feedback": feedback_by_link_only.get(inst["link_id"], []),
                    "badge": None,
                    "badge_label": None,
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
