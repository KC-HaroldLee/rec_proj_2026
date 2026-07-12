"""
사참위 권고 이행보고서(연도별 PDF)를 파싱해서 raw JSON으로 뽑아낸다.
DB에 바로 넣지 않고 중간 산출물(raw JSON)로 남겨서 검수 후 적재하기 위한 스크립트.

사용법: python3 scripts/parse_impl_report.py <year> <pdf_path>
예:     python3 scripts/parse_impl_report.py 2024 data/docs/rec/2024.pdf
"""
import sys
import re
import json
import csv
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
INST_CSV = ROOT / "data" / "parsed" / "rec" / "INST.csv"

# 원본 문서의 오타/표기 차이/줄임말을 INST.name으로 정규화하기 위한 별칭
# (예: 2025.pdf는 "해수부장관"처럼 줄임말을 씀)
ALIASES = {
    "기획재정부장관": "기획재정부",
    "행정안정부장관": "행정안전부 장관",  # 원문 오타(안정→안전)
    "산업부장관": "산업통상자원부 장관",
    "해수부장관": "해양수산부 장관",
    "행안부장관": "행정안전부 장관",
    "해경청장": "해양경찰청장",
    "국조실장": "국무조정실장",
    "인사처장": "인사혁신처장",
    "복지부장관": "보건복지부 장관",
    "고용부장관": "고용노동부 장관",
    "질병청장": "질병관리청장",
    "과기정통부장관": "과학기술 정보통신부 장관",
    "과기부장관": "과학기술 정보통신부 장관",
    "기재부장관": "기획재정부",
    "공정위원장": "공정거래위원장",
}

# "행안부·환경부·해수부장관"처럼 여러 기관이 "·"로 묶여 한 페이지에 같이
# 보고되는 경우 -> 기관별로 IMPL row를 따로 만들기 위한 별칭(리스트 반환)
COMBINED_ALIASES = {
    "행안부·환경부·해수부장관": ["행정안전부 장관", "환경부 장관", "해양수산부 장관"],
    "행안부장관·해경청장": ["행정안전부 장관", "해양경찰청장"],
    "해수부·행안부장관": ["해양수산부 장관", "행정안전부 장관"],
}

CONTENT_RE = re.compile(r"□\s*권고\s*내용")
STATUS_RE = re.compile(r"□\s*이행\s*(?:현황|내역)")
PLAN_RE = re.compile(r"□\s*향후\s*계획")
PAGE_FOOTER_RE = re.compile(r"-\s*\d+\s*-\s*$")


def load_inst_names():
    with open(INST_CSV, newline="", encoding="utf-8") as f:
        return [row["name"] for row in csv.DictReader(f)]


def build_header_regex(inst_names):
    def to_pattern(name):
        chars = list(name.replace(" ", ""))
        return r"\s*".join(re.escape(c) for c in chars)

    all_names = sorted(
        set(list(inst_names) + list(ALIASES.keys()) + list(COMBINED_ALIASES.keys())),
        key=len, reverse=True,
    )
    inst_alt = "|".join(to_pattern(n) for n in all_names)
    # 제목에 줄바꿈이 낄 수 있어 DOTALL, 최대 120자로 제한해 폭주 방지
    # non-greedy title이라 더 짧은 title로 매치되는 COMBINED_ALIASES(더 긴 문자열)가
    # 자연히 우선 시도됨 -> "행안부·환경부·해수부장관"을 마지막 토큰만 매치하는
    # 일 없이 통째로 잡아냄
    return re.compile(
        r"(?P<recno>\d+-\d+)\s+(?P<title>.{0,120}?)\s*(?:\((?P<seq>\d{1,2})\)\s*)?(?P<inst>"
        + inst_alt + r")",
        re.DOTALL,
    )


def canon_inst(raw, inst_names):
    """반환값은 항상 리스트(보통 원소 1개, 병합 헤더는 여러 개)."""
    raw_nospace = re.sub(r"\s+", "", raw)
    if raw_nospace in COMBINED_ALIASES:
        return COMBINED_ALIASES[raw_nospace]
    if raw_nospace in ALIASES:
        return [ALIASES[raw_nospace]]
    for n in inst_names:
        if n.replace(" ", "") == raw_nospace:
            return [n]
    return None


def to_markdown(body: str) -> str:
    """ㅇ/- /* / ※ 글머리기호를 마크다운으로 정리."""
    lines = [l.rstrip() for l in body.split("\n")]
    out = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if PAGE_FOOTER_RE.match(s):
            continue
        if s.startswith("ㅇ"):
            out.append("- " + s[1:].strip())
        elif s.startswith("※") or (s.startswith("*") and not s.startswith("**")):
            out.append("> " + s.lstrip("※*").strip())
        elif s.startswith("‧") or s.startswith("·"):
            out.append("    - " + s[1:].strip())
        elif s.startswith("-"):
            out.append("  - " + s[1:].strip())
        else:
            out.append(s)
    return "\n".join(out).strip()


def offset_to_page(offset, page_bounds):
    for pg, start, end in page_bounds:
        if start <= offset < end:
            return pg
    return page_bounds[-1][0] if page_bounds else None


def parse_pdf(pdf_path, year):
    inst_names = load_inst_names()
    header_re = build_header_regex(inst_names)

    page_texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            page_texts.append(p.extract_text() or "")

    full_text = ""
    page_bounds = []  # (page_num, start_offset, end_offset)
    for i, t in enumerate(page_texts):
        start = len(full_text)
        full_text += t + "\n"
        page_bounds.append((i + 1, start, len(full_text)))

    content_positions = [m.start() for m in CONTENT_RE.finditer(full_text)]

    # 각 entry의 헤더(recno/seq/inst/title) 찾기: □권고내용 직전 400자 윈도우에서 마지막 매치
    headers = []
    for cp in content_positions:
        window_start = max(0, cp - 400)
        window = full_text[window_start:cp]
        matches = list(header_re.finditer(window))
        if matches:
            m = matches[-1]
            inst_list = canon_inst(m.group("inst"), inst_names)
            title = re.sub(r"\s+", " ", m.group("title")).strip()
            headers.append({
                "recno": m.group("recno"),
                "seq": m.group("seq"),
                "inst_raw": m.group("inst"),
                "inst_list": inst_list,
                "title": title,
                "header_offset": window_start + m.start(),
            })
            continue

        # 표 셀 줄바꿈이 너무 꼬여서 recno 바로 뒤에 title/inst가 안 붙는 경우의
        # 최후 수단: "3-1"처럼 recno가 단독으로 한 줄을 차지하는 걸 찾고,
        # 윈도우 전체(공백 제거)에서 알려진 기관명/별칭 문자열을 검색
        recno_m = re.search(r"(?m)^\s*(\d+-\d+)\s*$", window)
        if recno_m:
            flat = re.sub(r"\s+", "", window)
            found = None
            for key, lst in COMBINED_ALIASES.items():
                if re.sub(r"\s+", "", key) in flat:
                    found = lst
                    break
            if found is None:
                for k, v in ALIASES.items():
                    if k in flat:
                        found = [v]
                        break
            if found is None:
                for n in inst_names:
                    if n.replace(" ", "") in flat:
                        found = [n]
                        break
            if found is not None:
                headers.append({
                    "recno": recno_m.group(1),
                    "seq": None,
                    "inst_raw": "(fallback)",
                    "inst_list": found,
                    "title": "",
                    "header_offset": window_start + recno_m.start(),
                })
                continue

        headers.append(None)

    entries = []
    skipped = []
    for i, cp in enumerate(content_positions):
        h = headers[i]
        if h is None or h["inst_list"] is None:
            skipped.append({"index": i, "offset": cp, "header": h})
            continue

        entry_end = content_positions[i + 1] if i + 1 < len(content_positions) else len(full_text)
        # 다음 entry의 헤더 시작 지점 전까지가 이 entry의 실제 본문 범위
        next_header_start = headers[i + 1]["header_offset"] if i + 1 < len(headers) and headers[i + 1] else entry_end
        body_end = min(entry_end, next_header_start)

        section_text = full_text[cp:body_end]
        sm = STATUS_RE.search(section_text)
        pm = PLAN_RE.search(section_text)

        if sm and pm:
            status_raw = section_text[sm.end():pm.start()]
            plan_raw = section_text[pm.end():]
        elif sm:
            status_raw = section_text[sm.end():]
            plan_raw = ""
        else:
            status_raw = ""
            plan_raw = ""

        status_md = to_markdown(status_raw)
        plan_md = to_markdown(plan_raw)
        page = offset_to_page(h["header_offset"], page_bounds)

        # 병합 헤더(예: 행안부·환경부·해수부장관)는 기관마다 IMPL row를 따로 생성,
        # status/plan 텍스트는 동일하게 공유
        for inst_name in h["inst_list"]:
            entries.append({
                "rec_no": h["recno"],
                "inst_name": inst_name,
                "title": h["title"],
                "year": year,
                "status": status_md or None,
                "plan": plan_md or None,
                "source": f"{Path(pdf_path).name}#page={page}",
            })

    return entries, skipped


def main():
    year = int(sys.argv[1])
    pdf_path = sys.argv[2]
    entries, skipped = parse_pdf(pdf_path, year)

    out_path = ROOT / "data" / "parsed" / "rec" / f"impl_{year}_raw.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"parsed entries: {len(entries)}")
    print(f"skipped (header not resolved): {len(skipped)}")
    for s in skipped:
        print("  ", s)
    print(f"written to {out_path}")


if __name__ == "__main__":
    main()
