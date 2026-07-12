from fastapi import APIRouter, Depends, Request

from app.categories import category_sort_key, resolve_category
from app.db import get_conn
from app.deps import require_login
from app.stuck import SUSPECT_SIMILARITY_THRESHOLD, trailing_streak
from app.templates_env import templates

router = APIRouter()


@router.get("/")
def dashboard(request: Request, category: str | None = None, user: dict = Depends(require_login)):
    selected_category, filter_category = resolve_category(category)

    with get_conn() as conn:
        by_category = sorted(
            conn.execute('SELECT category, COUNT(*) AS cnt FROM "REC" GROUP BY category').fetchall(),
            key=lambda r: category_sort_key(r["category"]),
        )
        categories = sorted(
            (r["category"] for r in conn.execute('SELECT DISTINCT category FROM "REC"').fetchall()),
            key=category_sort_key,
        )
        inst_count = conn.execute('SELECT COUNT(*) AS cnt FROM "INST"').fetchone()["cnt"]
        rec_inst_count = conn.execute('SELECT COUNT(*) AS cnt FROM "REC_INST"').fetchone()["cnt"]
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
            LIMIT 10
            '''
        ).fetchall()
        # docs/design-decisions.md "이행현황이 기관별로 다르게 오는지 여부"가 아직 미확인이라,
        # rec 단위로 뭉치지 않고 REC_INST 링크(권고+기관 조합) 단위로 행을 만든다.
        # LAG 윈도우 함수로 "바로 전 연도와 완전일치인지"(exact_same, SQL 완전일치 방식)와
        # "코사인 유사도"(similarity, 벡터 임베딩 방식)를 링크별 연도 시퀀스 안에서 한 번에
        # 계산한다. 두 방식 다 docs/design-decisions.md "복붙(정체) 탐지 방식" 참고.
        candidates = conn.execute(
            '''
            SELECT ri.link_id, r.rec_id, r.rec_no, r.content, i.name AS inst_name,
                   jsonb_agg(
                       jsonb_build_object(
                           'year', sub.year, 'status', sub.status,
                           'exact_same', sub.exact_same, 'similarity', sub.similarity
                       ) ORDER BY sub.year
                   ) AS years
            FROM (
                SELECT im.link_id, im.year, im.status,
                       (im.status = LAG(im.status) OVER w) AS exact_same,
                       CASE WHEN im.embedding IS NOT NULL AND LAG(im.embedding) OVER w IS NOT NULL
                            THEN 1 - (im.embedding <=> LAG(im.embedding) OVER w) END AS similarity
                FROM "IMPL" im
                WINDOW w AS (PARTITION BY im.link_id ORDER BY im.year)
            ) sub
            JOIN "REC_INST" ri ON ri.link_id = sub.link_id
            JOIN "REC" r ON ri.rec_id = r.rec_id
            JOIN "INST" i ON ri.inst_id = i.inst_id
            WHERE %(cat)s::text IS NULL OR r.category = %(cat)s::text
            GROUP BY ri.link_id, r.rec_id, r.rec_no, r.content, i.name
            ORDER BY ri.link_id
            ''',
            {"cat": filter_category},
        ).fetchall()

    # "정체" 배지는 과거 어느 시점의 반복이 아니라 "지금도 멈춰있는지"를 봐야 의미가 있어서,
    # 가장 최근 연도쌍(마지막 두 항목)이 완전일치/유사 중 하나라도 걸리는 링크만 남긴다.
    # 완전일치가 우선(🔴 확실한 증거), 아니면 유사도 임계값 이상을 의심 정황(🟡)으로.
    stuck_items = []
    for item in candidates:
        years = item["years"]
        if len(years) < 2:
            continue
        for y in years:
            y["same_as_prev"] = bool(y["exact_same"])
        latest = years[-1]
        if latest["exact_same"]:
            item["badge"] = "stuck"
            item["streak"] = trailing_streak([y["exact_same"] for y in years[1:]])
            item["badge_label"] = f"{item['streak']}년째 동일"
            item["sort_key"] = (2, item["streak"])
        elif latest["similarity"] is not None and latest["similarity"] >= SUSPECT_SIMILARITY_THRESHOLD:
            item["badge"] = "suspect"
            item["badge_label"] = f"실질 변화 없음 의심 (유사도 {latest['similarity']:.0%})"
            item["sort_key"] = (1, latest["similarity"])
        else:
            continue
        stuck_items.append(item)

    stuck_items.sort(key=lambda i: i["sort_key"], reverse=True)
    stuck_items = stuck_items[:20]

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "active_nav": "dashboard",
            "by_category": by_category,
            "total_recs": sum(row["cnt"] for row in by_category),
            "inst_count": inst_count,
            "rec_inst_count": rec_inst_count,
            "recent_feedback": recent_feedback,
            "ctx": "feed",
            "stuck_items": stuck_items,
            "categories": categories,
            "selected_category": selected_category,
        },
    )
