"""
REC_2022.pdf(사참위 권고집) "제3장 권고별 주요 내용" 파싱 스크립트.

전체 3개 분야(가습기살균제/세월호/재난일반)를 자동 파싱해서
관리번호 / 권고 / 대상 / 필요성 / 관련조사자료 구조로 마크다운 출력.

각주(*), 소제목(◦), 리스트(-) 처리 규칙은 core/parse/data-parsing-rules.md 기준.
"""
import re
import pymupdf

PDF_PATH = "data/docs/rec/REC_2022.pdf"
PAGE_START = 20  # 0-indexed, PDF 21페이지 (제3장 시작)
PAGE_END = 118   # 0-indexed, exclusive (PDF 118페이지까지 포함)

SECTIONS = [
    ("가습기살균제참사 분야", 26),
    ("4·16세월호참사 분야", 32),
    ("재난 및 피해지원 일반, 자료기록 분야", 22),
]

TABLE_HEADER_RE = re.compile(r"관리\s*\n?번호\s*\n?권\s*고\s*\n?대\s*상")
SECTION_TITLE_RE = re.compile(r"^\d\.\s.*(분야).*$")
BOILERPLATE_LINE_RES = [
    re.compile(r"^\d{1,4}$"),
    re.compile(r"^제\s?3\s?장$"),
    re.compile(r"^권고별 주요 내용$"),
    re.compile(r"^가습기살균제사건과 4[·・]16세월호참사 특별조사위원회 권고$"),
    SECTION_TITLE_RE,
]
NECESSITY_MARK_RE = re.compile(r"^□\s*필요성$")
RESEARCH_MARK_RE = re.compile(r"^□\s*관련\s*조사자료$")


def load_pages():
    doc = pymupdf.open(PDF_PATH)
    pages = []
    for i in range(PAGE_START, PAGE_END):
        text = doc[i].get_text().replace("\x07", "")
        pages.append((i + 1, text))  # 1-indexed pdf page (doc page, not printed page number)
    return pages


def build_full_text(pages):
    full_text = ""
    page_offsets = []
    for pnum, text in pages:
        page_offsets.append((len(full_text), pnum))
        full_text += text + "\n"
    return full_text, page_offsets


def page_at(page_offsets, pos):
    pg = page_offsets[0][1]
    for off, pn in page_offsets:
        if off <= pos:
            pg = pn
        else:
            break
    return pg


def strip_boilerplate(lines):
    out = []
    for l in lines:
        s = l.strip()
        if not s:
            continue
        if any(p.match(s) for p in BOILERPLATE_LINE_RES):
            continue
        out.append(l)
    return out


def split_record(cleaned_lines):
    """cleaned_lines(관리번호 제외, boilerplate 제거됨)를 gogo/target/necessity/research로 분리"""
    gogo, target, necessity, research = [], [], [], []
    section = "gogo"
    for l in cleaned_lines:
        s = l.strip()
        if NECESSITY_MARK_RE.match(s):
            section = "necessity"
            continue
        if RESEARCH_MARK_RE.match(s):
            section = "research"
            continue
        if section == "gogo" and s.startswith("◦"):
            section = "target"
        if section == "gogo":
            gogo.append(l)
        elif section == "target":
            target.append(l)
        elif section == "necessity":
            necessity.append(l)
        else:
            research.append(l)
    return gogo, target, necessity, research


MARKERS = {"-": "bullet", "◦": "subtitle", "*": "footnote", "※": "footnote"}


def group_items(lines):
    """마커(- ◦ * ※)로 시작하는 줄 기준으로 항목을 묶고, 줄바꿈으로 끊긴 문장은 이어붙인다.
    PDF 추출 특성상 줄바꿈 지점에 공백이 있으면 유지되고 없으면 그대로 이어지므로
    단순히 개행만 제거하면(구분자 없이 join) 원문이 복원된다."""
    items = []
    cur = None
    for line in lines:
        stripped = line.lstrip()
        marker = None
        for m in MARKERS:
            if stripped.startswith(m):
                marker = m
                break
        if marker:
            if cur is not None:
                items.append(cur)
            content = stripped[len(marker):]
            if content.startswith(" "):
                content = content[1:]
            cur = {"type": MARKERS[marker], "text": content}
        else:
            if cur is None:
                cur = {"type": "bullet", "text": ""}
            cur["text"] += line
    if cur is not None:
        items.append(cur)
    for it in items:
        it["text"] = it["text"].rstrip()
        if it["type"] in ("bullet", "subtitle") and it["text"].endswith("*"):
            it["text"] = it["text"][:-1].rstrip()
    return items


def render_necessity(lines):
    items = group_items(lines)
    md = []
    pending_footnotes = []

    def flush_footnotes():
        for fn in pending_footnotes:
            md.append("")
            md.append(f"  > {fn['text']}")
        pending_footnotes.clear()

    need_blank_before_bullet = True
    for it in items:
        if it["type"] == "footnote":
            pending_footnotes.append(it)
            need_blank_before_bullet = True
            continue
        flush_footnotes()
        if it["type"] == "subtitle":
            if md:
                md.append("")
            md.append(f"#### {it['text']}")
            md.append("")
            need_blank_before_bullet = False
        elif it["type"] == "bullet":
            if need_blank_before_bullet and md:
                md.append("")
            md.append(f"- {it['text']}")
            need_blank_before_bullet = False
    flush_footnotes()
    return "\n".join(md).strip()


def render_research(lines):
    items = group_items(lines)
    md = [f"- {it['text']}" for it in items if it["text"]]
    return "\n".join(md).strip()


def render_gogo(lines):
    # 첫 '-' 마커 전까지는 서술형 본문(권고 취지), 이후 '-'는 하위 세부 항목
    intro_lines = []
    rest_lines = []
    seen_marker = False
    for l in lines:
        if not seen_marker and l.lstrip().startswith("-"):
            seen_marker = True
        (rest_lines if seen_marker else intro_lines).append(l)

    intro = "".join(intro_lines).strip()
    items = group_items(rest_lines)
    parts = [intro] if intro else []
    if items:
        parts.append("\n".join(f"- {it['text']}" for it in items if it["text"]))
    return "\n\n".join(p for p in parts if p)


def render_target(lines):
    items = group_items(lines)
    return "\n".join(f"◦ {it['text']}" for it in items if it["text"])


def parse_all():
    pages = load_pages()
    full_text, page_offsets = build_full_text(pages)
    matches = list(TABLE_HEADER_RE.finditer(full_text))

    total_expected = sum(c for _, c in SECTIONS)
    if len(matches) != total_expected:
        raise ValueError(f"table header count mismatch: got {len(matches)}, expected {total_expected}")

    records = []
    for idx, m in enumerate(matches):
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        chunk = full_text[start:end]
        src_page = page_at(page_offsets, m.start())

        lines = chunk.split("\n")
        i = 0
        while i < len(lines) and not lines[i].strip():
            i += 1
        rec_no_raw = lines[i].strip()
        rest = lines[i + 1:]
        if not rec_no_raw.isdigit():
            raise ValueError(f"unexpected rec_no {rec_no_raw!r} near page {src_page}")

        cleaned = strip_boilerplate(rest)
        gogo, target, necessity, research = split_record(cleaned)

        records.append({
            "rec_no": int(rec_no_raw),
            "gogo": render_gogo(gogo),
            "target": render_target(target),
            "necessity": render_necessity(necessity),
            "research": render_research(research),
            "source": f"{PDF_PATH}#page={src_page}",
        })

    # 섹션별로 분리 (각 섹션은 관리번호가 1부터 다시 시작)
    sections_out = []
    cursor = 0
    for title, count in SECTIONS:
        chunk = records[cursor:cursor + count]
        seq = [r["rec_no"] for r in chunk]
        if seq != list(range(1, count + 1)):
            raise ValueError(f"{title}: rec_no sequence mismatch: {seq}")
        sections_out.append((title, chunk))
        cursor += count

    return sections_out


def to_markdown(title, records):
    out = [f"# {title}\n"]
    for r in records:
        out.append(f"## 관리번호 {r['rec_no']}\n")
        out.append("**권고**\n")
        out.append(r["gogo"] + "\n")
        out.append("**대상**\n")
        out.append(r["target"] + "\n")
        out.append("**필요성**\n")
        out.append(r["necessity"] + "\n")
        if r["research"]:
            out.append("**관련조사자료**\n")
            out.append(r["research"] + "\n")
        out.append(f"\n> source: {r['source']}\n")
        out.append("\n---\n")
    return "\n".join(out)


if __name__ == "__main__":
    sections_out = parse_all()
    out_dir = "../../data/scratch/rec"
    filenames = ["nes2-1", "nes2-2", "nes2-3"]
    for (title, records), fname in zip(sections_out, filenames):
        md = to_markdown(title, records)
        with open(f"{out_dir}/{fname}", "w", encoding="utf-8") as f:
            f.write(md)
        print(f"{fname}: {title} - {len(records)}건 작성 완료")
