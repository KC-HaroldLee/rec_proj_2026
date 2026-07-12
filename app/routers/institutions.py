from fastapi import APIRouter, Depends, HTTPException, Request

from app.categories import category_sort_key, resolve_category
from app.db import get_conn
from app.deps import require_login
from app.impl_timeline import fetch_institutions_timeline
from app.stuck import classify_year, compute_streak
from app.templates_env import templates

router = APIRouter()


@router.get("")
def institutions_list(
    request: Request,
    category: str | None = None,
    rec_no: str | None = None,
    user: dict = Depends(require_login),
):
    selected_category, filter_category = resolve_category(category)

    with get_conn() as conn:
        categories = sorted(
            (r["category"] for r in conn.execute('SELECT DISTINCT category FROM "REC"').fetchall()),
            key=category_sort_key,
        )
        # 권고번호 칩 목록 — 지금 선택된 카테고리에 속한 것만 (예: 세월호 선택 중이면 2-1, 2-2...).
        # "-" 앞뒤를 숫자로 쪼개서 진짜 순서대로 정렬 (recs.py와 동일한 이유).
        rec_options = conn.execute(
            '''
            SELECT rec_id, rec_no FROM "REC"
            WHERE %(cat)s::text IS NULL OR category = %(cat)s::text
            ORDER BY split_part(rec_no, '-', 1)::int, split_part(rec_no, '-', 2)::int
            ''',
            {"cat": filter_category},
        ).fetchall()

        selected_rec = None
        rec_institutions = []
        result = []

        if rec_no:
            # "권고번호로 필터" 모드: /institutions는 원래 기관 단위 집계 화면이지만,
            # "이 권고를 담당하는 기관들이 각각 어떻게 하고 있나"를 바로 보고 싶다는 요청으로
            # 추가함. recs.py의 권고 상세 페이지와 같은 데이터(app/impl_timeline.py)를 쓴다.
            selected_rec = conn.execute(
                'SELECT rec_id, rec_no, category, content FROM "REC" WHERE rec_no = %s', (rec_no,)
            ).fetchone()
            if not selected_rec:
                raise HTTPException(status_code=404, detail="권고를 찾을 수 없습니다.")
            rec_institutions = fetch_institutions_timeline(conn, selected_rec["rec_id"])
        else:
            # link(권고+기관) 단위로 연도별 status를 모아서 Python에서 정체 여부를 계산한다.
            # "이행률"이라는 표현은 쓰지 않는다 — status 텍스트가 바뀌었는지는 셀 수 있어도
            # 그게 실질적 이행완료인지는 시스템이 판단할 수 없다 (app/stuck.py 참고).
            # category로 필터하면 REC_INST/IMPL 카운트도 그 카테고리 범위로만 집계된다
            # (INST 자체엔 category가 없어서, REC를 거쳐야만 필터할 수 있다).
            link_rows = conn.execute(
                '''
                SELECT ri.inst_id, i.name AS inst_name, ri.link_id,
                       jsonb_agg(jsonb_build_object('year', im.year, 'status', im.status) ORDER BY im.year)
                           FILTER (WHERE im.impl_id IS NOT NULL) AS years
                FROM "REC_INST" ri
                JOIN "INST" i ON ri.inst_id = i.inst_id
                JOIN "REC" r ON ri.rec_id = r.rec_id
                LEFT JOIN "IMPL" im ON im.link_id = ri.link_id
                WHERE %(cat)s::text IS NULL OR r.category = %(cat)s::text
                GROUP BY ri.inst_id, i.name, ri.link_id
                ''',
                {"cat": filter_category},
            ).fetchall()

            institutions: dict[int, dict] = {}
            for row in link_rows:
                inst = institutions.setdefault(
                    row["inst_id"],
                    {"inst_id": row["inst_id"], "name": row["inst_name"], "rec_count": 0, "tracked": 0, "not_stuck": 0},
                )
                inst["rec_count"] += 1
                streak = compute_streak(row["years"] or [])
                if streak is None:
                    continue
                inst["tracked"] += 1
                if streak < 2:
                    inst["not_stuck"] += 1

            result = list(institutions.values())
            for inst in result:
                inst["not_stuck_rate"] = round(100 * inst["not_stuck"] / inst["tracked"]) if inst["tracked"] else None
            # public."INST"의 PK(inst_id) 순서 그대로 — 가나다순 정렬 안 함.
            result.sort(key=lambda i: i["inst_id"])

    return templates.TemplateResponse(
        request,
        "institutions/list.html",
        {
            "user": user,
            "active_nav": "institutions",
            "institutions": result,
            "categories": categories,
            "selected_category": selected_category,
            "rec_options": rec_options,
            "selected_rec": selected_rec,
            "rec_institutions": rec_institutions,
        },
    )


@router.get("/{inst_id}")
def institution_detail(
    inst_id: int, request: Request, category: str | None = None, user: dict = Depends(require_login)
):
    selected_category, filter_category = resolve_category(category)

    with get_conn() as conn:
        inst = conn.execute('SELECT * FROM "INST" WHERE inst_id = %s', (inst_id,)).fetchone()
        if not inst:
            raise HTTPException(status_code=404, detail="기관을 찾을 수 없습니다.")

        categories = sorted(
            (r["category"] for r in conn.execute('SELECT DISTINCT category FROM "REC"').fetchall()),
            key=category_sort_key,
        )

        # rec_no는 "2-10" 같은 문자열이라 그냥 ORDER BY하면 사전식 정렬이 된다 (/recs와 동일한 이유로).
        # exact_same/similarity: recs.py 상세페이지와 같은 LAG 방식 — 연도별 "신호등" 사각형을
        # 여기서도 보여달라는 요청으로 추가함 (권고 상세 페이지와 같은 배지 체계 공유).
        rows = conn.execute(
            '''
            SELECT r.rec_id, r.rec_no, r.content,
                   jsonb_agg(
                       jsonb_build_object(
                           'year', sub.year, 'status', sub.status,
                           'exact_same', sub.exact_same, 'similarity', sub.similarity
                       ) ORDER BY sub.year
                   ) FILTER (WHERE sub.impl_id IS NOT NULL) AS years
            FROM "REC_INST" ri
            JOIN "REC" r ON ri.rec_id = r.rec_id
            LEFT JOIN (
                SELECT im.link_id, im.impl_id, im.year, im.status,
                       (im.status = LAG(im.status) OVER w) AS exact_same,
                       CASE WHEN im.embedding IS NOT NULL AND LAG(im.embedding) OVER w IS NOT NULL
                            THEN 1 - (im.embedding <=> LAG(im.embedding) OVER w) END AS similarity
                FROM "IMPL" im
                WINDOW w AS (PARTITION BY im.link_id ORDER BY im.year)
            ) sub ON sub.link_id = ri.link_id
            WHERE ri.inst_id = %(inst_id)s
              AND (%(cat)s::text IS NULL OR r.category = %(cat)s::text)
            GROUP BY r.rec_id, r.rec_no, r.content
            ORDER BY split_part(r.rec_no, '-', 1)::int, split_part(r.rec_no, '-', 2)::int
            ''',
            {"inst_id": inst_id, "cat": filter_category},
        ).fetchall()

    recs = []
    tracked = not_stuck = 0
    for row in rows:
        years_raw = row["years"] or []
        years = []
        for i, y in enumerate(years_raw):
            badge, badge_label = classify_year(y["exact_same"], y["similarity"], is_first_report=(i == 0))
            years.append({"year": y["year"], "badge": badge, "badge_label": badge_label})

        latest = years[-1] if years else None
        if latest and latest["badge"] in ("stuck", "suspect", "progress"):
            tracked += 1
            if latest["badge"] != "stuck":
                not_stuck += 1

        recs.append(
            {
                "rec_id": row["rec_id"],
                "rec_no": row["rec_no"],
                "content": row["content"],
                "years": years,
                "latest_badge": latest["badge"] if latest else None,
                "latest_badge_label": latest["badge_label"] if latest else None,
                "latest_status": years_raw[-1]["status"] if years_raw else None,
            }
        )

    not_stuck_rate = round(100 * not_stuck / tracked) if tracked else None

    return templates.TemplateResponse(
        request,
        "institutions/detail.html",
        {
            "user": user,
            "active_nav": "institutions",
            "inst": inst,
            "recs": recs,
            "tracked": tracked,
            "not_stuck": not_stuck,
            "not_stuck_rate": not_stuck_rate,
            "categories": categories,
            "selected_category": selected_category,
        },
    )
