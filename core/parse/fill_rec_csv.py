"""
REC_일부.csv의 빈 necessity/source 컬럼을 parse_rec.py 파싱 결과로 채운다.
content(권고내용)는 이미 손으로 정리돼 있으므로 건드리지 않는다.

CSV 파일 안에서 개행은 실제 \n이 아니라 리터럴 "\n" 텍스트로, 리스트 항목의
"-"는 "\-"로 이스케이프해 한 레코드가 한 줄에 들어가도록 하는 기존 관례를
content 컬럼에서 확인했음 -> necessity도 동일한 관례를 따른다.
"""
import csv
from parse_rec import parse_all

CSV_PATH = "REC_일부.csv"


def escape_markdown(md_text: str) -> str:
    lines = md_text.split("\n")
    escaped = []
    for line in lines:
        if line.startswith("- "):
            line = "\\-" + line[1:]
        elif line == "-":
            line = "\\-"
        escaped.append(line)
    return "\\n".join(escaped)


def main():
    sections = parse_all()  # [(title, records), ...] 가습기/세월호/재난일반 순서

    lookup = {}
    for section_idx, (_title, records) in enumerate(sections, start=1):
        for r in records:
            key = f"{section_idx}-{r['rec_no']}"
            lookup[key] = {
                "necessity": escape_markdown(r["necessity"]),
                "source": r["source"],
            }

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    missing = []
    for row in rows:
        rec_no = row["rec_no"]
        if rec_no not in lookup:
            missing.append(rec_no)
            continue
        row["necessity"] = lookup[rec_no]["necessity"]
        row["source"] = lookup[rec_no]["source"]

    if missing:
        raise ValueError(f"매칭 안 된 rec_no: {missing}")

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)}행 업데이트 완료 ({CSV_PATH})")


if __name__ == "__main__":
    main()
