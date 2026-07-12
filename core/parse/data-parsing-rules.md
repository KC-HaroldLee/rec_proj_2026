# PDF 파싱 가이드

사참위 권고집, 연도별 이행보고서 PDF를 구조화 데이터(REC, IMPL 등)로 변환하기 위한
파싱 전략 가이드.

## 패키지 비교

| 패키지 | 설치 | 강점 | 약점 |
|---|---|---|---|
| **pdfplumber** | `pip install pdfplumber` | 텍스트 좌표 기반 추출, 표 인식(`extract_table`), 페이지 단위 세밀한 제어 | 스캔본(이미지 PDF)엔 무력, 속도는 보통 |
| **PyMuPDF (fitz)** | `pip install pymupdf` | 매우 빠름, 레이아웃 보존 좋음, 이미지 추출도 가능 | 표 추출은 pdfplumber보다 약함 |
| **pdftotext (poppler-utils)** | `sudo apt install poppler-utils` | 커맨드라인으로 빠르게 원문 확인 가능(`-layout` 옵션) | 파이썬 라이브러리 아님, 세밀한 파싱엔 한계, 이미 1차 확인용으로 사용해봄 |
| **camelot** | `pip install camelot-py` | 표 추출 특화, 격자형 표에 강함 | 표가 없는 서술형 문서엔 불필요, Ghostscript 등 추가 의존성 필요 |

## 추천 조합

**메인: `pdfplumber`**

이유:
- 지금 문서들이 "□ 권고 내용", "□ 이행 현황", "□ 향후 계획" 같은 **고정 마커**로 섹션이
  구분되어 있어서, 텍스트를 좌표 순서대로 뽑은 뒤 마커 기준으로 잘라내는 방식이 잘 맞음
- "2-2 표(관리번호/권고/대상)" 같은 표 형식 구간은 `extract_table()`로 바로 표 구조 추출 가능
- 스캔본이 아니라 텍스트 기반 PDF(가습기살균제/세월호 법령·보고서 전부 그러함)이므로
  OCR 불필요

**보조: `pdftotext -layout`** — 파싱 로직 짜기 전에 빠르게 원문 구조를 눈으로 확인할 때 계속 활용

## 설치

```bash
pip install pdfplumber
```

## 기본 사용법

```python
import pdfplumber

with pdfplumber.open("2024_가습기살균제사건과_4_16세월호참사.pdf") as pdf:
    for page_num, page in enumerate(pdf.pages, start=1):
        text = page.extract_text()
        print(f"--- page {page_num} ---")
        print(text)
```

## 이 프로젝트 문서 구조에 맞춘 파싱 전략

### 1. 이행보고서 (연도별, "□ 권고 내용 / □ 이행 현황 / □ 향후 계획" 패턴)

```python
import re
import pdfplumber

def parse_impl_report(pdf_path, year):
    records = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text is None:
                continue

            # 항목 헤더 패턴: "2-1  세월호참사 관련 공식 사과 등  (1) 대통령"
            header_match = re.search(
                r'(\d+-\d+)\s+(.+?)\s+\((\d+)\)\s*(\S+)',
                text
            )
            if not header_match:
                continue

            rec_no, title, order, inst_name = header_match.groups()

            # 섹션 마커 기준으로 자르기
            content_match = re.search(r'□\s*권고\s*내용(.+?)□\s*이행\s*현황', text, re.S)
            status_match  = re.search(r'□\s*이행\s*현황(.+?)□\s*향후\s*계획', text, re.S)
            plan_match    = re.search(r'□\s*향후\s*계획(.+?)$', text, re.S)

            records.append({
                "rec_no": rec_no,
                "inst_name": inst_name,
                "content": content_match.group(1).strip() if content_match else None,
                "status": status_match.group(1).strip() if status_match else None,
                "plan": plan_match.group(1).strip() if plan_match else None,
                "year": year,
                "source": f"{pdf_path}#page={page_num}",
            })
    return records
```

**주의**: 실제 문서는 페이지 경계에서 섹션이 끊기는 경우가 있음(권고내용이 페이지를
넘어가는 등). `page.extract_text()`를 페이지 단위로만 처리하면 이런 경우 놓칠 수 있으니,
전체 텍스트를 이어붙인 뒤 정규식을 적용하는 방식도 고려할 것.

```python
def parse_impl_report_v2(pdf_path, year):
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        page_markers = []  # (문자 위치, 페이지번호) 기록해서 나중에 source 추적
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            page_markers.append((len(full_text), page_num))
            full_text += text + "\n"

    # 항목 단위로 분리 (다음 관리번호/항목 헤더가 나오기 전까지)
    entries = re.split(r'(?=\d+-\d+\s+.+?\(\d+\))', full_text)
    # 이후 entries 각각에 위 정규식 파싱 로직 적용
    return entries
```

### 2. 사참위 권고집 (표 형식: 관리번호 / 권고 / 대상)

```python
def parse_recommendation_table(pdf_path):
    records = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # row 예상 형태: [관리번호, 권고내용, 대상]
                    if row and row[0] and row[0].strip().isdigit():
                        records.append({
                            "rec_no": row[0].strip(),
                            "content": row[1].strip() if row[1] else None,
                            "inst_raw": row[2].strip() if row[2] else None,  # "ㅇ 국회의장" 등 여러 줄
                            "source": f"{pdf_path}#page={page_num}",
                        })
    return records
```

`inst_raw`는 "ㅇ 국정원장\nㅇ 경찰청장..." 형태로 여러 줄일 수 있으므로,
후처리로 `ㅇ` 기준 분리해서 REC_INST에 여러 행으로 넣어야 함:

```python
def split_institutions(inst_raw: str) -> list[str]:
    lines = inst_raw.split("\n")
    return [line.lstrip("ㅇ○ ").strip() for line in lines if line.strip()]
```

### 3. "필요성" / "관련조사자료" 섹션 (마크다운 변환 대상)

이미지에서 확인된 구조:
```
□ 필요성
- 본문...
  * 각주 (들여쓰기 + 별표)

□ 관련조사자료
- 「자료제목」 결과보고서
```

```python
def to_markdown(necessity_raw: str) -> str:
    lines = necessity_raw.split("\n")
    md_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("*"):
            # 각주는 블록인용으로
            md_lines.append(f"> {stripped.lstrip('*').strip()}")
        elif stripped.startswith("-"):
            md_lines.append(f"- {stripped.lstrip('-').strip()}")
        else:
            md_lines.append(stripped)
    return "\n".join(md_lines)
```

## 검증 팁

- 파싱 스크립트 다 만들고 나서, **전체 개수를 먼저 세어볼 것**
  (예: "세월호참사 분야는 32건이어야 하는데 실제로 몇 개 파싱됐는지" 확인)
  목차에 나온 숫자(가습기 26건, 세월호 32건, 재난일반 22건)와 대조하면
  파싱 누락을 빠르게 발견할 수 있음
- 정규식이 문서마다 100% 들어맞지 않을 수 있으므로, 파싱 실패한 페이지는
  로그로 남겨서 나중에 수동으로 확인
  ```python
  failed_pages = []
  # 파싱 실패 시 failed_pages.append(page_num) 하고 마지막에 출력
  ```

## 각주 처리 규칙 (확정)

원문에서 각주는 다음 시각적 패턴으로 나타남:
- 본문 문장 끝에 `*` 표시
- 다음 줄에 들여쓰기된 `* 각주내용`

**예시 (원문)**
```
이처럼 국가가 책임과 역할을 다하지 못해 가습기살균제참사가 발생했고, 해결이 지연
됐음에도 이에 대한 구체적인 책임을 인정하거나 사과한 바 없음.*
* 2017년 8월 문재인 대통령의 사과는 정부의 구체적인 과오를 인정하는 것으로 보기는 어려움.
```

**변환 후 (마크다운)**
```markdown
- 이처럼 국가가 책임과 역할을 다하지 못해 가습기살균제참사가 발생했고, 해결이 지연됐음에도 이에 대한 구체적인 책임을 인정하거나 사과한 바 없음.

  > 2017년 8월 문재인 대통령의 사과는 정부의 구체적인 과오를 인정하는 것으로 보기는 어려움.
```

- 각주는 **직전 문장(리스트 항목)에 종속**되는 것으로 처리하고, 블록인용(`>`)을 해당
  리스트 항목 아래에 들여써서 배치한다. 이렇게 하면 렌더링 시 "이 각주가 위 항목의
  부연설명"이라는 게 시각적으로도 드러남.
- 탐지 정규식 예시:
  ```python
  import re

  def extract_footnote(text):
      # 본문 문장 끝의 * 표시 + 다음 줄의 "* 각주내용" 패턴
      match = re.search(r'([^\n]+?)\*\s*\n\s*\*\s*(.+)', text)
      if match:
          main_sentence = match.group(1).strip()
          footnote = match.group(2).strip()
          return main_sentence, footnote
      return text, None
  ```

## 알려진 오타/추출 오류 패턴

실제 문서를 파싱하며 반복 확인된 오류 유형. 파싱 후처리 단계에서 검토 필요.

| 패턴 | 예시 | 추정 원인 |
|---|---|---|
| "해" → "헤" 오인식 | "위헤" (→위해), "재검토헤" (→재검토해) | 폰트/추출 과정에서 모음 오인식 |
| 음절 탈락 | "법행위가" (→불법행위가) | 글자 하나가 통째로 누락 |
| 단독 자모 삽입 | "개선하기 ㅗ바랍니다" (→바랍니다) | 불완전한 자모가 글자 사이 삽입 |

**대응 방안**: 완벽한 자동 교정은 어려우므로,
1. 흔한 오타 사전(치환 테이블)을 만들어 알려진 패턴은 자동 치환
2. 정상적인 한글 음절 조합이 아닌 문자(단독 자모 등)가 감지되면 해당 레코드에
   "검토 필요" 플래그를 달아 사람이 확인하도록 함
   ```python
   import re

   def flag_suspicious_text(text):
       # 단독 자모(ㅗ, ㅜ, ㅏ 등)가 완성형 글자 사이에 끼어있는 경우 감지
       if re.search(r'[가-힣][ㄱ-ㅎㅏ-ㅣ][가-힣]', text):
           return True  # 검토 필요
       return False
   ```

## 문단/리스트 구분 규칙 (확정)

원문은 `.` 뒤에 공백 없이 `-`가 바로 붙어 리스트 항목이 이어지는 경우가 많고,
리스트가 끝난 뒤 완전히 다른 주제의 문단("아울러, ~")이 구분자 없이 이어지기도 함.

**변환 규칙**:
1. 첫 리스트 항목 앞: `\n\n- ` (문단 구분 + 리스트 시작)
2. 이후 리스트 항목들 사이: `\n- `
3. 리스트가 끝나고 새 문단(예: "아울러,")이 시작되는 지점: `\n\n` (빈 줄로 문단 구분)

```python
import re

def format_list(text):
    # 첫 하이픈 앞엔 문단 구분(빈 줄)
    text = re.sub(r'(?<=\.)-\s*', '\n\n- ', text, count=1)
    # 이후 하이픈들은 줄바꿈만
    text = re.sub(r'(?<=\.)-\s*', '\n- ', text)
    return text
```

**레코드 분리 여부**: 같은 관리번호 안에서 여러 기관에게 서로 다른 내용을 요구하거나
("대통령은 사과, 환경부장관은 배·보상"), 주도/협조 관계가 섞여 있어도("A는 추진,
B는 협조") 원문에 관리번호가 나뉘어 있지 않다면 **하나의 REC로 유지**하고, 텍스트
안에서 문단 구분만 한다. 관리번호가 곧 레코드 분리의 기준.

## 기관명 정규화 규칙 (확정)

"환경부 장관"(띄어쓰기) / "환경부장관"(붙여쓰기) 표기가 문서마다, 심지어 같은
문서 안에서도 혼재함. 이는:
- SQL 조회(완전일치 비교)에서는 전혀 보정되지 않음 — 다른 기관으로 취급되어
  조회 누락 위험 있음
- 벡터 임베딩/RAG 쪽은 서브워드 단위 처리로 어느 정도 관대하게 처리되나,
  완전히 무시되는 것은 아니고 미세한 차이는 남음

**대응**: INST 테이블에 저장하기 전 공백 제거 등으로 정규화하여 동일 기관으로
인식되도록 처리. (docs/schema.md의 INST 테이블 설계 참고)

## 소제목(◦) 처리 규칙 (확정)

일부 REC의 `necessity`(필요성)가 여러 소주제로 나뉘어 서술되는 경우, `◦` 기호로
소제목을 표시하고 그 아래 `-` 리스트로 세부 근거를 나열하는 2단계 구조가 나타남.

**원문 패턴**
```
◦ 독성정보 관리의 필요성- 가습기살균제참사에서 유해 화학물질 독성정보 확보 및
관리가 미흡했음이 드러났음...- 가습기살균제참사 이후 화학물질의 관리강화를 위해...
◦ 독성연구 및 관리전담기관의 설치- 국내 독성연구의 경우...
```

`◦`(소제목)와 `-`(하위 근거)는 위계가 다르며, `◦`가 상위 섹션 제목 역할을 함.

**변환 후 (마크다운)**
```markdown
#### 독성정보 관리의 필요성

- 가습기살균제참사에서 유해 화학물질 독성정보 확보 및 관리가 미흡했음이 드러났음...
- 가습기살균제참사 이후 화학물질의 관리강화를 위해...

#### 독성연구 및 관리전담기관의 설치

- 국내 독성연구의 경우 현재 식약처 소관 독성연구에 국한되는 흐름이...
```

`◦`를 `####`(소제목)로 변환하는 이유: 하나의 REC 안에 여러 소주제가 섞여 있을 때,
전부 `-` 리스트로만 평평하게 처리하면 실제로는 다른 주제인데 같은 위계처럼 보이는
문제가 생김. 소제목으로 구분하면 "이 권고가 몇 개의 근거 축으로 구성되는지"가
렌더링 시 한눈에 드러남.

**처리 순서 주의**: `◦` 뒤에도 `-`가 바로 붙어 있는 경우가 있으므로
(`◦ 제목- 내용...`), 반드시 `◦` 치환을 먼저 하고 `-` 리스트 치환을 나중에 적용해야 함.

```python
import re

def format_subsection(text):
    # 1. ◦로 시작하는 줄을 소제목(####)으로 변환 (먼저 처리)
    text = re.sub(r'◦\s*', '\n\n#### ', text)
    # 2. 그 다음 하이픈 리스트 처리 (기존 format_list 규칙 적용)
    text = re.sub(r'(?<=\.)-\s*', '\n\n- ', text, count=1)
    text = re.sub(r'(?<=\.)-\s*', '\n- ', text)
    return text
```

## 아직 확인 필요한 것

- 연도별 이행보고서 PDF의 항목 헤더 패턴이 매년 완전히 동일한 포맷인지
  (2023, 2024는 확인됐으나 향후 연도는 서식이 바뀔 수 있음 — 정규식이 깨질 가능성 대비)
- 표 형식 페이지(관리번호/권고/대상)와 서술형 페이지(권고내용/필요성/관련조사자료)가
  같은 PDF 안에 섞여 있는지, 별도 문서인지 확인 필요
