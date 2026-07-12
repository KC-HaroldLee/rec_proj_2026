"""
data/parsed/rec/impl_<year>_raw.json (parse_impl_report.py 또는 vision OCR로 생성한 raw data)를
IMPL 테이블에 넣기 위한 SQL을 생성한다.

rec_no + inst_name을 자연키로 삼아 REC_INST.link_id를 SELECT 서브쿼리로 찾아서 INSERT.

사용법: python3 scripts/load_impl.py <json_path> [<json_path> ...] | \
        docker compose exec -T db psql -U rec_admin -d rec_proj -v ON_ERROR_STOP=1
"""
import sys
import json
from pathlib import Path


def esc(v):
    if v is None or v == "":
        return "NULL"
    return "'" + v.replace("'", "''") + "'"


def main():
    paths = sys.argv[1:]
    out = ["BEGIN;"]
    total = 0
    for path in paths:
        with open(path, encoding="utf-8") as f:
            entries = json.load(f)
        out.append(f"-- {Path(path).name} ({len(entries)} rows)")
        for e in entries:
            out.append(
                'INSERT INTO "IMPL" ("link_id", "year", "status", "plan", "source") '
                'SELECT ri.link_id, '
                f'{e["year"]}, {esc(e.get("status"))}, {esc(e.get("plan"))}, {esc(e.get("source"))} '
                'FROM "REC_INST" ri '
                'JOIN "REC" r ON ri.rec_id = r.rec_id '
                'JOIN "INST" i ON ri.inst_id = i.inst_id '
                f'WHERE r.rec_no = {esc(e["rec_no"])} AND i.name = {esc(e["inst_name"])};'
            )
            total += 1
    out.append("COMMIT;")
    print("\n".join(out))
    print(f"-- total rows: {total}", file=sys.stderr)


if __name__ == "__main__":
    main()
