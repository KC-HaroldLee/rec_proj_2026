"""RAG 검색 결과 rows를 검색결과 페이지에서 표로 보여주고, 근거 레코드로 바로
이동할 수 있게 컬럼 이름으로 링크를 추정해 붙인다.

LLM이 만든 SQL의 SELECT 목록은 매번 다르므로 완벽할 수 없다 — rec_id/inst_id처럼
이 프로젝트에서 상세 페이지가 있는 컬럼만 링크로, 나머지는 그냥 텍스트로 보여준다.
"""

_LINK_COLUMNS = {
    "rec_id": "/recs/{}",
    "inst_id": "/institutions/{}",
}


def build_result_table(rows: list[dict]) -> tuple[list[str], list[list[dict]]]:
    if not rows:
        return [], []

    columns: list[str] = []
    for row in rows:
        for k in row.keys():
            if k not in columns:
                columns.append(k)

    table_rows = []
    for row in rows:
        cells = []
        for col in columns:
            value = row.get(col)
            url_template = _LINK_COLUMNS.get(col)
            url = url_template.format(value) if url_template and value is not None else None
            cells.append({"value": value, "url": url})
        table_rows.append(cells)

    return columns, table_rows
