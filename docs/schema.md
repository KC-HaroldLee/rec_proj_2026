# 스키마 정의서

사참위(사회적참사특별조사위원회) 권고 이행보고 시민 모니터링 시스템의 데이터베이스 스키마.
DBMS: PostgreSQL

## 테이블 개요 (총 10개)

| 테이블 | 역할 |
|---|---|
| INST | 기관 (권고 대상) |
| REC | 권고 (사참위 원본) |
| REC_INST | 권고↔기관 연결 (다대다) |
| IMPL | 이행보고 (연도별) |
| EVID | 관련조사자료 |
| REC_EVID | 권고↔조사자료 연결 (다대다) |
| AUTH | 계정 (팀원 로그인) |
| FEEDBACK | 시민 피드백 |
| FEEDBACK_EVIDENCE | 피드백 근거자료 링크 (1:N) |
| TERM | 용어사전 |

## ERD 관계 요약

```
INST ──┐
       ├── REC_INST ──┐
REC ───┘              │
  │                    ├── IMPL ── FEEDBACK ── AUTH
  ├── REC_EVID ──┐     │              │
EVID ─────────────┘    │              └── FEEDBACK_EVIDENCE
                        │
AUTH ── TERM (작성자/수정자)
```

## 1. INST (기관)

책임/권고 대상이 되는 기관. 정부조직 개편으로 이름이 자주 바뀌므로,
조직 위계(상하관계)는 모델링하지 않고 "권고 대상이었다는 사실"만 기록한다.

```sql
CREATE TABLE "INST" (
    "inst_id"  SERIAL PRIMARY KEY,           -- 기관ID
    "name"     VARCHAR(100) NOT NULL,        -- 기관명 (원문 그대로)
    "note"     TEXT NULL                     -- 비고 (조직개편 이력 메모 등)
);
```

**note 컬럼 활용 예시**: "2025.10.1 이후 재정경제부/기획예산처로 분리 추정(비공식)"

## 2. REC (권고)

사참위가 발간한 권고사항 원문.

```sql
CREATE TABLE "REC" (
    "rec_id"      SERIAL PRIMARY KEY,        -- 권고ID
    "category"    VARCHAR(50) NOT NULL,      -- 분야: 가습기살균제/세월호참사/재난및피해지원일반
    "rec_no"      VARCHAR(20) NOT NULL,      -- 권고번호 (원문 기준, 예: "2-1")
    "content"     TEXT NOT NULL,             -- 권고내용
    "necessity"   TEXT NULL,                 -- 필요성 (마크다운, 각주 포함 가능)
    "source"      VARCHAR(200) NULL          -- 출처 (파일명#page=번호 형식 권장)
);
```

**necessity는 마크다운으로 저장.** 각주는 블록인용(`>`)으로 표현해 원문 서식을 최대한 보존한다.

## 3. REC_INST (권고-기관 연결)

권고 하나에 대상기관이 여러 개(예: 9개) 붙을 수 있고,
같은 기관이 여러 권고의 대상이 될 수 있어 다대다 관계로 설계.

```sql
CREATE TABLE "REC_INST" (
    "link_id"  SERIAL PRIMARY KEY,
    "rec_id"   INTEGER NOT NULL,
    "inst_id"  INTEGER NOT NULL,
    CONSTRAINT "FK_REC_INST_REC"  FOREIGN KEY ("rec_id")  REFERENCES "REC" ("rec_id"),
    CONSTRAINT "FK_REC_INST_INST" FOREIGN KEY ("inst_id") REFERENCES "INST" ("inst_id"),
    CONSTRAINT "UQ_REC_INST" UNIQUE ("rec_id", "inst_id")
);
```

## 4. IMPL (이행보고)

연도별 이행현황/향후계획. `REC_INST`의 각 연결(권고+기관 조합)마다
연도별로 별도 보고가 달릴 수 있다는 전제로 설계 (기관별로 답변이 다를 수 있음을 대비).

```sql
CREATE TABLE "IMPL" (
    "impl_id"          SERIAL PRIMARY KEY,
    "link_id"          INTEGER NOT NULL,     -- REC_INST 참조
    "year"             INTEGER NOT NULL,
    "status"           TEXT NULL,            -- 이행현황
    "plan"             TEXT NULL,            -- 향후계획
    "source"           VARCHAR(200) NULL,
    "embedding"        vector(768) NULL,     -- status 임베딩 (정체 탐지 2번 방식, 아래 참고)
    "embedding_model"  VARCHAR(50) NULL,     -- 임베딩을 만든 모델명
    CONSTRAINT "FK_IMPL_REC_INST" FOREIGN KEY ("link_id") REFERENCES "REC_INST" ("link_id"),
    CONSTRAINT "UQ_IMPL" UNIQUE ("link_id", "year")
);
```

**벡터 임베딩 기반 정체 탐지** (`core/similarity/`): `embedding`/`embedding_model`은
pgvector 확장(`core/similarity/schema.sql`)이 있어야 쓸 수 있다. Chroma 같은 별도
벡터DB 대신 이 컬럼에 직접 저장하기로 한 이유는 design-decisions.md 참고 — 필요한
연산이 "링크 내 인접 연도 1:1 코사인 비교"뿐이라 최근접 이웃 검색용 인덱스가 필요
없었다. `core/similarity/backfill.py`가 `status`를 임베딩해 채워 넣고,
`app/routers/dashboard.py`가 `<=>` 연산자로 인접 연도 유사도를 계산해 대시보드의
"의심 정황"(🟡) 배지에 쓴다.

**미확인 사항**: 여러 기관이 걸린 권고에서 이행현황이 실제로 기관별로 다르게 오는지,
아니면 통짜로 한 번만 오는지는 아직 확인 안 됨. 후자로 밝혀지면 관련 REC_INST 각각에
동일 값을 복사해 넣는 방식으로 운용.

## 5. EVID (관련조사자료)

```sql
CREATE TABLE "EVID" (
    "evid_id"  SERIAL PRIMARY KEY,
    "code"     VARCHAR(50) NULL,             -- 자료코드 (예: "직가-1")
    "title"    VARCHAR(300) NOT NULL
);
```

## 6. REC_EVID (권고-조사자료 연결)

한 권고가 조사자료를 여러 개 가질 수 있고(예: 관리번호 19번은 2개),
같은 조사자료가 여러 권고에서 공유되기도 함(예: 관리번호 5, 6번이 자료 공유) → 다대다 확정.

```sql
CREATE TABLE "REC_EVID" (
    "link_id"  SERIAL PRIMARY KEY,
    "rec_id"   INTEGER NOT NULL,
    "evid_id"  INTEGER NOT NULL,
    CONSTRAINT "FK_REC_EVID_REC"  FOREIGN KEY ("rec_id")  REFERENCES "REC" ("rec_id"),
    CONSTRAINT "FK_REC_EVID_EVID" FOREIGN KEY ("evid_id") REFERENCES "EVID" ("evid_id"),
    CONSTRAINT "UQ_REC_EVID" UNIQUE ("rec_id", "evid_id")
);
```

## 7. AUTH (계정)

팀원 20명 개인별 로그인. URL 비공개 + 소규모 신뢰 그룹이므로
정식 회원가입/비밀번호 찾기 등은 만들지 않고, 관리자가 계정을 미리 생성해 배포하는 방식.

```sql
CREATE TABLE "AUTH" (
    "auth_id"       SERIAL PRIMARY KEY,
    "auth_name"     VARCHAR(50) NOT NULL,
    "password_hash" VARCHAR(64) NOT NULL     -- SHA-256, salt 포함 권장
);
```

## 8. FEEDBACK (시민 피드백)

이행보고에 대한 문제제기. "정부가 이행완료라 했지만 실제로는..." 같은
검증 기록을 쌓기 위한 테이블.

`link_id`(REC_INST)는 항상 채운다. `impl_id`는 특정 연도 보고를 겨냥한 피드백일 때만
채우고, 이행보고 자체가 아직 한 번도 없는 (기관, 권고) 조합에 대한 피드백(예:
국회의장처럼 아무 응답도 안 한 기관)은 `impl_id`를 NULL로 둔다. IMPL 테이블에 "안
냈다"는 뜻의 가짜 row를 넣지 않기로 한 이유: IMPL은 뱃지 계산(LAG 비교)·임베딩·
대시보드가 참조하는 "실제 제출된 보고" 테이블이라, 합성 row를 섞으면 그 로직들이
오염된다. 2026-07-15에 impl_id 단독 FK에서 이 구조로 변경.

```sql
CREATE TABLE "FEEDBACK" (
    "feedback_id"  SERIAL PRIMARY KEY,
    "link_id"      INTEGER NOT NULL,
    "impl_id"      INTEGER NULL,
    "auth_id"      INTEGER NOT NULL,
    "content"      TEXT NOT NULL,
    "created_at"   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "FK_FEEDBACK_REC_INST" FOREIGN KEY ("link_id") REFERENCES "REC_INST" ("link_id"),
    CONSTRAINT "FK_FEEDBACK_IMPL" FOREIGN KEY ("impl_id") REFERENCES "IMPL" ("impl_id"),
    CONSTRAINT "FK_FEEDBACK_AUTH" FOREIGN KEY ("auth_id") REFERENCES "AUTH" ("auth_id")
);
```

## 8-1. FEEDBACK_EVIDENCE (피드백 근거자료 링크)

피드백 하나에 근거 링크를 여러 개 달 수 있도록 분리한 자식 테이블
(원래는 `FEEDBACK.evidence_url` 단일 컬럼이었으나 2026-07-14에 1:N으로 정규화).
피드백이 삭제되면 근거 링크도 같이 지워진다(`ON DELETE CASCADE`).

```sql
CREATE TABLE "FEEDBACK_EVIDENCE" (
    "evidence_id"  SERIAL PRIMARY KEY,
    "feedback_id"  INTEGER NOT NULL,
    "url"          VARCHAR(300) NOT NULL,
    CONSTRAINT "FK_FEEDBACK_EVIDENCE_FEEDBACK"
        FOREIGN KEY ("feedback_id") REFERENCES "FEEDBACK" ("feedback_id") ON DELETE CASCADE
);
```

## 9. TERM (용어사전)

팀원들이 자유롭게 추가/수정하는 용어 사전. 사전적 정의뿐 아니라
"이 프로젝트/사회적참사 맥락에서의 특수한 의미"까지 별도로 기록한다.
예: "애도"는 세월호참사 맥락에서 국가 애도 표명 방식 논쟁과 얽힌 사회적 함의를 가짐.

```sql
CREATE TABLE "TERM" (
    "term_id"       SERIAL PRIMARY KEY,
    "term"          VARCHAR(100) NOT NULL,
    "definition"    TEXT NOT NULL,           -- 사전적/일반적 의미
    "context"       TEXT NULL,               -- 이 프로젝트 맥락에서의 의미
    "category"      VARCHAR(50) NULL,        -- 사회적개념/법률용어/기관약칭 등
    "created_by"    INTEGER NOT NULL,
    "created_at"    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updated_by"    INTEGER NULL,
    "updated_at"    TIMESTAMP NULL,
    "is_deleted"    BOOLEAN DEFAULT FALSE,   -- 실제 삭제 대신 숨김 처리
    CONSTRAINT "FK_TERM_CREATED_BY" FOREIGN KEY ("created_by") REFERENCES "AUTH" ("auth_id"),
    CONSTRAINT "FK_TERM_UPDATED_BY" FOREIGN KEY ("updated_by") REFERENCES "AUTH" ("auth_id")
);
```

## 인덱스 (조회 편의)

```sql
CREATE INDEX "idx_rec_no"       ON "REC" ("rec_no");
CREATE INDEX "idx_impl_year"    ON "IMPL" ("year");
CREATE INDEX "idx_impl_status"  ON "IMPL" ("status");
CREATE INDEX "idx_feedback_impl" ON "FEEDBACK" ("impl_id");
CREATE INDEX "idx_feedback_link" ON "FEEDBACK" ("link_id");
CREATE INDEX "idx_feedback_evidence_feedback" ON "FEEDBACK_EVIDENCE" ("feedback_id");
```

## 대표 쿼리 예시

**몇 년째 이행현황이 동일한 항목 찾기 (완전일치 기준)**
```sql
SELECT a.link_id, a.year AS year1, b.year AS year2
FROM "IMPL" a
JOIN "IMPL" b ON a.link_id = b.link_id AND a.year < b.year
WHERE a.status = b.status;
```

**특정 기관 관련 권고 전체 조회**
```sql
SELECT r.content
FROM "INST" i
JOIN "REC_INST" ri ON i.inst_id = ri.inst_id
JOIN "REC" r ON ri.rec_id = r.rec_id
WHERE i.name = '국정원장';
```

**특정 조사자료가 인용된 권고 전체 조회**
```sql
SELECT r.rec_no, r.content
FROM "EVID" e
JOIN "REC_EVID" re ON e.evid_id = re.evid_id
JOIN "REC" r ON re.rec_id = r.rec_id
WHERE e.code = '직가-1';
```
