# 진행 히스토리 (PC 이전용 인수인계 문서)

이 문서는 다른 PC로 옮긴 뒤 새로 시작하는 Claude Code 세션이 "지금까지 뭘 했고,
뭐가 남았고, 새 PC에서 뭘 다시 해야 하는지"를 빠르게 파악하기 위한 것이다.
**"왜 이렇게 결정했는지"의 상세 근거는 `design-decisions.md`에 있으니 중복 설명하지
않고 포인터만 남긴다.** 이 문서는 시간순 진행 로그 + 새 PC 체크리스트에 집중한다.

## 0. 프로젝트 한 줄 요약

사참위 권고 이행 모니터링 시스템. 자세한 배경은 `project-overview.md` 참고.
스택: **FastAPI + Jinja2 + HTMX** (프론트), **PostgreSQL + pgvector** (DB, 벡터 포함),
**Ollama 로컬 LLM** (text-to-SQL 질의응답 + 임베딩), Docker Compose로 DB만 컨테이너화.

## 1. 지금까지 한 일 (시간순)

1. **`.gitignore` 정리 + 스크래치 파일 정리** — 루트에 흩어져 있던 이름 없는
   파싱 테스트 덤프(`1`, `2`, `nes2-1` 등)를 `data/scratch/rec/`로 이동,
   `parse_rec.py`의 출력 경로도 수정. `.env`, `__pycache__/`, `data/docs/`(원본 PDF),
   `data/scratch/` 등을 gitignore 처리. `data/parsed/`(REC.csv 등 파싱 결과)는
   git에 포함하기로 결정.

2. **프론트엔드 스택 결정** — React 대신 FastAPI+Jinja2+HTMX. 근거는
   `design-decisions.md` "프론트엔드: React 대신 FastAPI + Jinja2 + HTMX로
   시작하는 이유" 참고.

3. **`app/` 스캐폴딩** — FastAPI 앱 뼈대(`main.py`, `db.py`, `deps.py`,
   `routers/`, `templates/`, `static/`) 생성. htmx는 CDN 대신 로컬 vendoring
   (`app/static/js/htmx.min.js`). 로그인은 세션 쿠키(`SessionMiddleware`) +
   `AUTH.password_hash`(SHA-256) 대조.

4. **대시보드 "정체 탐지" (완전일치 기준)** — `app/stuck.py`에 streak 계산 로직.
   행 단위는 REC(권고)가 아니라 **REC_INST 링크(권고+기관 조합)** — 기관별로 이행현황이
   다를 수 있다는 전제(`design-decisions.md` "이행현황이 기관별로 다르게 오는지 여부"
   참고, 아직 미확인 사항). 연도별 dot 시각화, "N년째 동일" 배지.
   - **버그 하나 실사용 중 발견/수정**: 동일 연도쌍 탐지 SQL이 pair 수만큼 IMPL 행을
     중복시켜 "9년째 동일" 같은 말도 안 되는 값이 나온 적 있음 → CTE로 분리해서 해결.

5. **`core/rag/` — text-to-SQL 자연어 질의** (`ollama-guide.md`의 패턴을 따름).
   - `schema_context.py`: 프롬프트용 스키마 설명. **`AUTH` 테이블은 아예 안 보여줌**.
   - `sql_guard.py`: LLM이 만든 SQL 1차 검증(SELECT/WITH 단일 문장, 위험 키워드·AUTH
     차단) — 이게 유일한 방어선은 아님.
   - **`rec_readonly`라는 별도 Postgres 롤**을 만들어서(`core/rag/readonly_role.sql`)
     실제 실행 권한 자체를 SELECT-only로 제한, AUTH는 GRANT도 안 함, read-only
     트랜잭션 강제. 문자열 검증이 뚫려도 DB 권한에서 다시 막히는 이중 방어.
   - `qa.py`: 질문 → SQL 생성 → 검증 → 실행 → 결과를 다시 LLM에 넣어 자연어 답변,
     2단계 파이프라인.

6. **권고 상세 페이지 완성** (`app/templates/recs/detail.html`) — `REC.content`/
   `necessity`를 마크다운 렌더링(`app/markdown_render.py`, CSV 이스케이프 `\n`/`\-`
   원상복구 먼저 필요했음 — `core/parse/fill_rec_csv.py`의 관례). 기관별 연도별
   이행현황 타임라인 + 시민 피드백 목록/작성 폼.

7. **기관별 현황: "이행률" 대신 "정체 아님 비율"** — IMPL에 완료 여부 컬럼이 없어서
   "이행완료율"을 계산하는 건 정부 자기보고 텍스트를 곧이곧대로 믿는 셈이라 이 프로젝트
   취지와 상충. 대신 "status가 전년도와 달라졌는가"만 객관적으로 세는 지표로 대체.
   상세 페이지에서는 권고별 행마다 배지 + 최신 연도 status 원문을 나란히 표시.
   (`app/stuck.py`의 로직을 대시보드와 공유하도록 리팩터링.)

8. **용어사전 수정/삭제 UI** — htmx로 행 단위만 교체(`term_row.html` ↔
   `term_row_edit.html`). 삭제는 실제 DELETE 아니라 `is_deleted` 소프트 삭제
   (schema.md 설계 그대로). 작성자 제한 없음 — 팀원 20명 모두 서로 수정 가능한
   전제(`project-overview.md`에 명시).

9. **검색 결과 페이지 분리** — 대시보드 검색창을 htmx 부분 응답에서 `GET /search?q=`
   로 이동하는 일반 폼 제출로 변경(북마크/새로고침 가능하도록). `app/search_render.py`가
   SQL 결과 컬럼명이 `rec_id`/`inst_id`면 자동으로 상세 페이지 링크로 바꿔서
   "근거 레코드" 표를 만듦.

10. **벡터 유사도 라우팅 (정체 탐지 2번 방식)** —
    - **Chroma 대신 Postgres `pgvector` 확장 선택**. 필요한 연산이 "많은 벡터 중
      최근접 찾기"가 아니라 "같은 링크의 인접 연도 1:1 코사인 비교"뿐이라 별도
      벡터DB가 불필요하다고 판단. `docker-compose.yml`의 이미지를
      `postgres:16` → **`pgvector/pgvector:pg16`**으로 교체(기존 볼륨 데이터 보존 확인,
      collation version mismatch는 `ALTER DATABASE ... REFRESH COLLATION VERSION`
      + `REINDEX`로 해결).
    - `core/similarity/schema.sql`: `CREATE EXTENSION vector`, `IMPL.embedding
      vector(768)`, `IMPL.embedding_model` 컬럼 추가.
    - `core/similarity/embed.py`, `backfill.py`: Ollama `nomic-embed-text`로
      `IMPL.status` 임베딩 생성·저장. **275건 백필 완료 (11.8초 소요)**.
    - `app/routers/dashboard.py`: SQL `LAG` 윈도우 함수로 "바로 전 연도와
      완전일치"(🔴 "N년째 동일")와 "코사인 유사도"(🟡 "실질 변화 없음 의심 NN%")를
      한 쿼리에서 계산. 임계값 0.93 (`app/stuck.py`의
      `SUSPECT_SIMILARITY_THRESHOLD`) — `scripts/test_embedding_similarity.py`
      실측치(근사재탕 0.9501 / 네거티브컨트롤 0.8462) 기준 보수적으로 설정.
      **실데이터 검증 중 임계값 경계(0.93~0.94)에서 오탐 후보 1건 발견** — "의심"이지
      "확정"이 아니라고 배지 문구에 명시하고 원문+유사도%를 그대로 보여줘서 사람이
      판단하게 하는 것으로 이 부정확성을 흡수하는 설계. 데이터 더 쌓이면 재조정 필요.

11. **정리 작업** — 와이어프레임 목업(`login-wireframe.html`, `dashboard-wireframe.html`)
    삭제(실제 템플릿으로 대체됐으므로), 루트의 문서 8개를 `docs/`로 이동하고
    `README.md`만 루트에 남김(`.env.example` 신규 추가), 보안 점검(`core/rag/
    readonly_role.sql`에 비밀번호 평문 하드코딩된 것 발견 → 즉시 교체 + psql 변수
    주입 방식으로 재작성 — 4번 항목에 상세 기록).

12. **text-to-SQL 평탄화 뷰 추가 + 모델 한계 확인** — 실제 브라우저로 검색 기능을
    쓰다가 `llama3.2:1b`가 `INST.rec_id` 같은 존재하지 않는 컬럼을 지어내며 JOIN을
    틀리는 걸 발견. `core/rag/views.sql`에 `rec_inst_flat`/`impl_flat` 평탄화 뷰를
    만들어서(REC×REC_INST×INST, IMPL까지 포함) JOIN 자체를 안 해도 되게 했고
    `rec_readonly`에 GRANT SELECT 완료. **다만 이걸로도 완전히 해결 안 됨** —
    "대통령 담당 권고 보여줘" 같은 질문에서 이 모델이 한국어 기관명을
    `WHERE source = '-president'`처럼 존재하지도 않는 영어 슬러그로 지어내는 걸
    확인. SQL 문법/JOIN 문제가 아니라 "질문 속 고유명사 → 쿼리 조건" 매핑 자체를
    못 하는 모델 근본 한계로 판단하고 프롬프트 튜닝은 중단함. **부작용으로 발견한 것**:
    스키마 프롬프트에 few-shot 예시나 긴 설명을 추가하니 이 모델이 오히려 질문을
    되풀이하며 여러 답을 만드는 등 더 무너짐 — `core/rag/schema_context.py`는
    일부러 짧게 유지 중, 나중에도 이 습관 유지할 것. 뷰 자체는 남겨둠(JOIN
    컬럼 hallucination은 확실히 줄었고, 더 나은 모델로 바꾸면 바로 도움 됨).
    **다음 PC에서 더 큰 모델(exaone3.5:7.8b, qwen2.5:14b, 또는 llama3.2:3b)로
    바꿔서 이 부분 재검증할 것** — 사용자가 "더 좋은 PC로 옮기고 나서 해보겠다"고
    보류함(2026-07-12).

13. **임베딩 모델 재검증(bge-m3, multilingual-e5-large) → nomic-embed-text로 원복
    확정** — "정체 탐지"에 더 나은 한국어 멀티링구얼 모델을 써보려고 두 모델 다
    실측(A/B 근사재탕 쌍, C 네거티브컨트롤, link 7 vs 22 실제 사례 비교)했으나 둘 다
    관공서 문체 특성상 전반적으로 유사도가 높게 뭉쳐서(중앙값 0.96~0.99) 재탕/실질변화
    구분력이 `nomic-embed-text`(중앙값 0.97, 그나마 갭 있음)보다 못하다는 걸 확인.
    `IMPL.embedding`을 `vector(768)`(nomic 기준)로 최종 원복, 269건 재백필 완료.
    상세 근거는 `design-decisions.md`에 안 남기고 이 로그에만 기록 — 재시도할 사람은
    이 항목부터 보고 시간 낭비하지 말 것.

14. **`rec_readonly` 비밀번호 드리프트 발견/수정** — `.env`의 `RAG_DB_PASSWORD`와
    실제 DB 롤 비밀번호가 어긋나 `/search`가 "Ollama에 연결하지 못했습니다"로
    오진단되는 걸 발견(실제 원인은 DB 인증 실패인데 에러 메시지가 부정확했음).
    `core/rag/readonly_role.sql` 재실행으로 동기화. **교훈**: `.env`를 손으로 갈아치운
    뒤엔 이 SQL도 같이 재실행해야 한다는 걸 다음 사람이 잊기 쉬움.

15. **SQL 실행 에러 메시지를 사용자용으로 순화** — `core/rag/qa.py`가 원본 Postgres
    에러(`column t2.rec_no does not exist` 등)를 그대로 노출하던 걸
    "질문을 이해하지 못했어요. 다르게 표현해서 다시 물어봐 주세요."로 교체. 근본 원인
    (모델이 잘못된 SQL을 만드는 것) 자체는 안 고침 — 프롬프트를 더 손대면 오히려 이
    모델이 무너진다는 12번 항목의 교훈 때문에 일부러 프롬프트는 안 건드림.

16. **자연어 검색(`/search`) 잠금 + Ollama 서비스 완전 종료 (2026-07-12)** — 실사용
    테스트 중 "몇 개야?" 류가 아니라 "왜 이렇게 됐어?" 같은 설명·추론형 질문이 진짜
    니즈로 드러남. 이건 법 조문/사참위 종합보고서 원문 같은 근거 문서가 있어야 답할 수
    있는데 지금 레포엔 그런 문서가 전혀 없고, 근거 없이 로컬 소형 모델에게 시키면
    그럴듯한 헛소리(환각)를 만들 위험이 큼(`llama3.2:1b`가 존재하지 않는 테이블/컬럼을
    지어내는 것도 이번에 재확인). 상세 근거는 `design-decisions.md`
    "자연어 검색(`/search`) 잠금" 항목 참고.
    - `app/routers/search.py`: `core.rag.qa` import 자체를 제거하고 고정 안내 메시지만
      반환하도록 변경 (이 라우트에서 Ollama를 호출할 코드 경로가 없음).
    - 대시보드/`/search` 페이지의 검색창 UI(`search-block`)도 완전히 제거.
    - Ollama 서비스: `sudo systemctl stop ollama && sudo systemctl disable ollama`로
      끄고 자동시작도 해제함. **재개 조건**: 법 조문+종합보고서 원문 확보, 그리고
      로컬 소형 모델로는 이 추론을 못 하므로 사실상 Claude API 병행이 필요해 보임.
    - **주의**: `python3 -m core.similarity.backfill`(임베딩, "정체 탐지"용)은
      Ollama가 켜져 있어야 동작한다 — 채팅 기능만 잠갔지 임베딩 기능까지 잠근 게
      아니므로, 새 데이터 임베딩이 필요하면 그때만 `sudo systemctl start ollama`로
      잠깐 켜고 끝나면 다시 꺼둘 것.

17. **발견했지만 아직 안 고침**: 대시보드 "정체된 권고 항목"에서 유사도 기반
    "의심"(🟡) 배지가 뜬 행은 연도 점(`year-dot`)이 하나도 하이라이트 안 됨 —
    `app/routers/dashboard.py`의 `y["same_as_prev"] = bool(y["exact_same"])`가
    완전동일(🔴)일 때만 점을 칠하고 유사도 기반 매치는 반영을 안 해서다. 배지 텍스트
    (유사도 %)는 뜨는데 점이 아무것도 안 칠해져서 "어느 연도끼리 비슷하다는 건지"가
    시각적으로 안 보이는 상태. 다음에 이어서 고칠 것.

18. **git 저장소 아직 없음** — 이 프로젝트 폴더는 GitHub에서 zip으로 받은 상태라
    `.git`이 없다. 기존에 있던 저장소로 push해야 하는데, 저장소 URL/remote 연결
    작업은 아직 착수만 하고 못 끝냄 — 다음 세션에서 이어서 할 것.

19. **피드백 입력에 최소 마크다운 지원 추가 (2026-07-13~14, 커밋 `8d6d8bf`)** —
    기존 피드백 작성/수정 폼이 `<input type=text>` 한 줄이라 불편하다는 실사용
    피드백으로 시작. 리치 에디터(TipTap 등)는 이 프로젝트에 JS 번들러가 아예 없어서
    도입 자체가 빌드 파이프라인부터 새로 까는 인프라 작업이 되므로 과하다고 판단,
    대신 `<textarea>`(rows=10) + 순수 JS 버튼 3개(굵게/기울임/목록)짜리 최소 툴바만
    추가(`app/static/js/feedback-toolbar.js`, 라이브러리 없음, `document` 이벤트
    위임이라 htmx로 폼이 통째로 교체돼도 재바인딩 불필요).
    - **저장형 XSS 방지**: `FEEDBACK.content`는 로그인한 사용자 누구나 입력하는
      값이라 REC/IMPL(신뢰된 CSV 적재 데이터)과 다르게 취급해야 함. 기존
      `render_markdown()`을 그대로 썼다면 python-markdown이 raw HTML을 그대로
      통과시켜 `<script>` 삽입이 가능했음 → `app/markdown_render.py`에
      `render_feedback_markdown()`을 새로 추가해 `html.escape()`로 `<`/`>` 등을
      먼저 이스케이프한 뒤 markdown을 렌더링(마크다운 문법 `**`, `-` 자체는 안
      건드림). `**중요**` + `<script>alert(1)</script>`를 실제로 넣어서 `<strong>`은
      렌더되고 스크립트는 `&lt;script&gt;`로 이스케이프되는 것까지 curl로 검증,
      테스트 계정/데이터는 검증 후 삭제(작업 방식 습관대로).
    - **목록 렌더링 함정**: python-markdown은 목록 바로 앞에 빈 줄이 없으면 새
      블록으로 안 잡고 그냥 텍스트 취급(문단 중간에서 `- `로 시작해도 무시됨) —
      목록 버튼 클릭 시 필요하면 빈 줄을 자동으로 채워 넣도록 처리.
    - **버튼이 textarea 포커스/선택영역을 뺏는 버그 발견/수정**: 브라우저가 버튼
      `mousedown` 시점에 포커스를 그 버튼으로 옮겨버려서, 클릭 핸들러가 실행될 땐
      이미 `textarea.selectionStart/End`가 틀어져 있었음 → `mousedown`에
      `preventDefault()`를 걸어 포커스가 계속 textarea에 남게 해서 해결.
    - **들여쓰기(탭) 버튼은 시도했다가 제외**: NBSP(줄어들지 않는 공백)로 들여쓰기를
      흉내 내는 버튼을 만들었으나, 사용자가 "거추장스럽다"며 제거 요청 — 들여쓰기는
      사용자가 직접 스페이스로 입력하는 것으로 최종 결정, 관련 코드 전부 제거함.
    - **나중에 리치 에디터가 진짜 필요해지면**: React 계열(TipTap/Slate)은 번들러
      도입이 전제라 피하고, EasyMDE/Trix처럼 `<script src>` 한 줄로 붙는(번들러
      불필요) 라이브러리를 먼저 고려할 것.

**작업 방식 관련 습관**: 매 기능마다 실제 DB에 테스트 계정/데이터를 넣어서 curl로
로그인→기능→결과까지 실제로 돌려보고, 끝나면 테스트 계정/데이터를 지우는 식으로
검증했다. 새 PC에서도 이 방식을 유지하는 게 좋다 (스키마만 보고 짐작하지 말 것).
**2026-07-12 세션에서 만든 `test`/`test` 로그인 계정은 안 지우고 남겨뒀음** — 다음
세션에서 실사용 계정만 남기고 정리할 것.

## 2. 지금 검증된 상태 (이 PC 기준)

- DB: `REC` 80건, `IMPL` 277건, `INST` 25건, `IMPL.embedding` 275건 채워짐
  (2건은 status가 NULL이라 제외).
- 라우트 전부 실제 로그인 세션으로 curl 테스트 통과: `/`, `/recs/{id}`,
  `/institutions`, `/institutions/{id}`, `/terms` (+ CRUD), `/search?q=`,
  `/impl/{id}/feedback`.
- `rec_readonly` 롤 권한 직접 확인: `AUTH` SELECT 거부, `INSERT` read-only
  트랜잭션 에러로 거부됨.
- `AUTH`에 실사용 로그인 계정 1개 생성됨(`admin`) — 볼륨을 그대로 옮기면 같이 옮겨짐.
  비밀번호는 이 문서에 안 적음(만든 사람만 앎), 잊었으면 새로 `UPDATE "AUTH" SET
  password_hash = ...`로 바꿀 것.
- 개발 서버는 포트 8000이 아니라 **8001**로 띄웠음 — 이 PC에 `portainer`라는
  무관한 도커 컨테이너가 8000을 이미 쓰고 있어서. 새 PC에서 8000이 비어있으면
  README.md 대로 8000 써도 됨.

## 3. ⚠️ 새 PC에서 반드시 다시 해야 하는 것 (git에 안 옮겨지는 것들)

### 3-1. `.env` 파일 (gitignore됨, 통째로 새로 만들어야 함)

`.env.example`을 복사해서 채우면 됨(`cp .env.example .env`, README.md 참고).
`RAG_DB_PASSWORD`는 `core/rag/readonly_role.sql`을 실행할 때 `-v
rag_db_password="$RAG_DB_PASSWORD"`로 넘기는 값과 같아야 함 — **이 SQL 파일 자체에는
비밀번호를 평문으로 넣지 않는다** (2026-07-12에 실수로 하드코딩했다가 발견해서 psql
변수 주입 방식으로 고침 + 노출된 비밀번호는 즉시 교체함, `4. 보안 점검` 참고).
`OLLAMA_CHAT_MODEL`은 아래 3-2 참고 — 이 PC는 VRAM 6GB라 `llama3.2:1b`로 낮춰뒀음.

### 3-2. Ollama 모델 재설치

**16번 항목 참고 — 자연어 검색(`/search`)이 지금 잠겨있어서 채팅 모델(`exaone3.5:7.8b`
등)은 당장 필수가 아니다.** "정체 탐지" 임베딩만 쓸 거면 이거면 됨:
```bash
ollama pull nomic-embed-text          # 임베딩용, 필수, 가벼움(274MB)
```
채팅 모델은 나중에 `/search`를 다시 열기로 하면(법 조문/종합보고서 근거 문서 확보 후)
그때 받으면 됨 — `ollama-guide.md`, `design-decisions.md` "자연어 검색 잠금" 항목 참고.
Ollama 자체도 이 PC에서는 `systemctl stop/disable`로 꺼둔 상태였으니, 새 PC에서
설치했다면 임베딩 백필 끝난 뒤 필요 없으면 마찬가지로 꺼둘지 판단할 것.
`.env`의 `OLLAMA_CHAT_MODEL`은 나중에 채팅 모델을 실제로 pull하면 그 이름과 맞출 것
(지금은 `llama3.2:1b`로 남아있어도 안 쓰이니 무해함).

### 3-3. DB 데이터 (docker volume이라 git에 없음)

`pgdata`는 named volume이라 `git clone`으로 안 옮겨진다. 옵션 두 가지:

- **A. 볼륨 통째로 옮기기** (지금 데이터 그대로 유지하고 싶으면):
  ```bash
  # 이 PC에서
  docker run --rm -v rec_proj_pgdata:/data -v $(pwd):/backup alpine \
    tar czf /backup/pgdata_backup.tar.gz -C /data .
  # 새 PC로 pgdata_backup.tar.gz 옮긴 뒤
  docker volume create rec_proj_pgdata
  docker run --rm -v rec_proj_pgdata:/data -v $(pwd):/backup alpine \
    tar xzf /backup/pgdata_backup.tar.gz -C /data
  ```
- **B. 처음부터 다시 파싱/적재** — `data/parsed/rec/*.csv`, `impl_*_raw.json`은
  git에 있으니 `db-schema.sql` → `scripts/load_initial.py` → `scripts/load_impl.py`
  순서로 재적재 가능 (원본 PDF는 `data/docs/`에 없으므로 재파싱은 안 됨, 이미 파싱된
  결과만 재적재 가능).

어느 쪽이든 이후 **`core/rag/readonly_role.sql`, `core/similarity/schema.sql`을
반드시 다시 실행**해야 한다 (롤/확장/컬럼은 볼륨 복사 시 같이 옮겨지지만, A안이 아니라
스키마부터 새로 만드는 B안이면 필수).

### 3-4. 임베딩 재생성 (A안으로 볼륨을 그대로 옮겼으면 불필요)

B안(재적재)을 택했거나 `IMPL.embedding`이 비어 있으면:
```bash
python3 -m core.similarity.backfill
```

### 3-5. `docker-compose.yml`은 이미 pgvector 이미지로 커밋되어 있음 (git에 포함, 추가 조치 불필요)

## 4. 보안 점검 기록 (2026-07-12)

git 커밋 전에 "알려지면 위험한 정보가 담긴 파일이 있는지" 점검을 요청받아 전체
트리를 훑었다. **`core/rag/readonly_role.sql`에 `rec_readonly` 비밀번호가 평문으로
하드코딩되어 있었음** — 이 파일은 `.env`와 달리 gitignore 대상이 아니라서, 그대로
커밋했으면 git 히스토리에 영구히 남을 뻔했다.

**조치**: 새 비밀번호로 즉시 교체(`ALTER ROLE`) + `.env` 갱신 + SQL 파일은 psql 변수
주입 방식(`ALTER ROLE rec_readonly PASSWORD :'rag_db_password';`, 실행 시
`-v rag_db_password="$RAG_DB_PASSWORD"`로 넘김)으로 재작성해서 평문이 파일에 남지
않게 고침. TCP 접속으로 새/틀린 비밀번호 둘 다 실제로 테스트해서 확인
(`docker compose exec`로 테스트하면 컨테이너 내부 유닉스 소켓 trust 인증 때문에
비밀번호 검증을 건너뛰어 잘못된 결과가 나오니 주의 — 반드시 TCP로 테스트할 것).

그 외 나머지 파일(`.env`는 정상적으로 gitignore됨, `.memo/`는 공개 설치 가이드라
민감정보 없음, 나머지 코드/문서에는 하드코딩된 시크릿 없음)은 문제 없었음.

**DB 백업(볼륨 tar)을 git에 커밋하지 말 것** — 검토 결과 `data/parsed/`(git 추적
대상, 536KB)에 비해 Postgres 데이터 디렉토리 전체는 65MB로 100배 이상 크고 거의
다 바이너리 오버헤드. 게다가 시민 피드백(`FEEDBACK`)이 쌓이면 팀원 실명 등이 DB
안에 들어가는데 이걸 git 히스토리에 영구 보존하는 건 피하는 게 맞다. `data/docs/`
(원본 PDF)를 gitignore한 것과 같은 논리 — 볼륨 백업은 git 바깥(USB/클라우드)에서
관리 (3-3 참고).

## 5. 개발 서버 실행 순서 (새 PC 공통)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d db
# 처음 띄우는 볼륨이면: core/rag/readonly_role.sql, core/similarity/schema.sql 실행
uvicorn app.main:app --reload
```
테스트 로그인 계정이 없으면 `AUTH`에 하나 수동으로 넣어야 함
(`password_hash = sha256(password)`, salt 없음 — `design-decisions.md` 참고).

## 6. 남은 것 / 다음 후보

- `features-backlog.md`의 "검토/보류 중인 기능": 검증 항목 자동 분해(LLM), 권고 간
  관계, 알림/구독, 감사로그, 자유 태그, 첨부파일 관리 — 전부 미착수.
- 벡터 유사도 임계값(0.93) 재조정 — 위 1번 항목의 오탐 사례 참고, 데이터 더 쌓이면.
- "이행현황이 기관별로 다르게 오는지" 미확인 사항 — 실제 2023~2025 문서 더 봐야 확정
  (`design-decisions.md` 참고). 확정되면 대시보드/기관상세의 "링크 단위 행" 설계를
  재검토할 수 있음.
- 정식 배포 환경(팀원 20명 실사용) 관련 미정: 계정 발급 방식 운영 절차, `.env` 시크릿
  관리 방법, HTTPS/리버스프록시 등은 아직 논의 안 함.

## 7. 문서 지도 (이 프로젝트의 .md 파일들이 각각 뭘 담당하는지)

| 문서 | 역할 |
|---|---|
| `README.md` | **git clone 직후 여기부터** — 셋업 명령어 순서 |
| `project-overview.md` | 프로젝트가 왜 존재하는지, 핵심 가치 |
| `design-decisions.md` | **"왜 이렇게 했는지"의 상세 근거** — 이 문서(PROGRESS.md)에서 요약만 하고 넘어간 모든 결정의 전체 설명이 여기 있음 |
| `schema.md`, `db-schema.sql` | DB 스키마 정의 (pgvector 컬럼 포함, 최신 상태) |
| `screen-design.md` | 화면별 구성/디자인 톤, 완성된 화면 목록 |
| `ollama-guide.md` | Ollama 설치/API/모델 선택 가이드 |
| `core/parse/data-parsing-rules.md` | PDF → 구조화 데이터 파싱 규칙 |
| `features-backlog.md` | 아이디어 백로그 (미착수 기능들) |
| **`PROGRESS.md` (이 문서)** | 시간순 진행 로그 + PC 이전 체크리스트 |
