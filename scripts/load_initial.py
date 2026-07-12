import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "parsed" / "rec"


def esc(v):
    if v is None or v == "":
        return "NULL"
    return "'" + v.replace("'", "''") + "'"


def main():
    out = ["BEGIN;"]

    with open(DATA_DIR / "INST.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out.append('-- INST (%d rows)' % len(rows))
    for r in rows:
        out.append(
            f'INSERT INTO "INST" ("name", "note") VALUES ({esc(r["name"])}, {esc(r.get("note"))});'
        )

    with open(DATA_DIR / "REC.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out.append('-- REC (%d rows)' % len(rows))
    for r in rows:
        out.append(
            'INSERT INTO "REC" ("category", "rec_no", "content", "necessity", "source") '
            f'VALUES ({esc(r["category"])}, {esc(r["rec_no"])}, {esc(r["content"])}, '
            f'{esc(r.get("necessity"))}, {esc(r.get("source"))});'
        )

    with open(DATA_DIR / "REC_INST.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out.append('-- REC_INST (%d rows)' % len(rows))
    for r in rows:
        out.append(
            'INSERT INTO "REC_INST" ("rec_id", "inst_id") '
            f'SELECT r.rec_id, i.inst_id FROM "REC" r, "INST" i '
            f'WHERE r.rec_no = {esc(r["rec_no"])} AND i.name = {esc(r["inst_name"])};'
        )

    out.append("COMMIT;")
    print("\n".join(out))


if __name__ == "__main__":
    main()
