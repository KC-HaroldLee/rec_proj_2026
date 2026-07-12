"""REC 하나에 대해, 대상기관별 연도별 이행현황 + 신호등 배지를 계산하는 공유 쿼리.

recs.py(권고 상세 페이지)와 institutions.py(/institutions?rec_no=... 필터)가
"권고 하나 -> 대상기관들 각각의 연도별 배지"라는 같은 모양의 데이터를 필요로 해서
뽑아냈다. LAG 기반 exact_same/similarity 계산은 app/routers/dashboard.py와 같은 패턴.
"""
from app.stuck import classify_year

_TIMELINE_SQL = '''
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
    ORDER BY i.inst_id, sub.year
'''


def fetch_institutions_timeline(conn, rec_id: int) -> list[dict]:
    """rec_id 하나에 대해 [{inst_id, name, years: [...], latest_badge, latest_badge_label,
    latest_status}, ...]를 inst_id 순서로 반환한다."""
    rows = conn.execute(_TIMELINE_SQL, (rec_id,)).fetchall()

    institutions: dict[int, dict] = {}
    for row in rows:
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
                    "status": row["status"],
                    "plan": row["plan"],
                    "source": row["source"],
                    "badge": badge,
                    "badge_label": badge_label,
                }
            )

    result = list(institutions.values())
    for inst in result:
        latest = inst["years"][-1] if inst["years"] else None
        inst["latest_badge"] = latest["badge"] if latest else None
        inst["latest_badge_label"] = latest["badge_label"] if latest else None
        inst["latest_status"] = latest["status"] if latest else None
    result.sort(key=lambda i: i["inst_id"])
    return result
