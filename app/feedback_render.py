"""FEEDBACK 행에 표시용 부가 필드(content_html, evidence_urls)를 붙이는 공통 헬퍼.

partials/feedback_item.html이 recs/dashboard/feedback 라우터 세 곳에서 공유되고,
근거 링크는 FEEDBACK_EVIDENCE에 1:N으로 저장되므로 N+1 쿼리를 피하려고 배치로 붙인다.
"""
from app.markdown_render import render_feedback_markdown


def attach_feedback_extras(conn, rows) -> None:
    if not rows:
        return

    ev_rows = conn.execute(
        'SELECT feedback_id, url FROM "FEEDBACK_EVIDENCE" WHERE feedback_id = ANY(%s) ORDER BY evidence_id',
        ([row["feedback_id"] for row in rows],),
    ).fetchall()

    urls_by_feedback: dict[int, list[str]] = {}
    for ev in ev_rows:
        urls_by_feedback.setdefault(ev["feedback_id"], []).append(ev["url"])

    for row in rows:
        row["content_html"] = render_feedback_markdown(row["content"])
        row["evidence_urls"] = urls_by_feedback.get(row["feedback_id"], [])
