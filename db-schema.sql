-- ============================================
-- 사참위 권고 이행보고 모니터링 시스템 스키마 (PostgreSQL)
-- ============================================

-- 1. 기관 (책임/대상 기관)
CREATE TABLE "INST" (
    "inst_id"  SERIAL PRIMARY KEY,           -- 기관ID
    "name"     VARCHAR(100) NOT NULL,        -- 기관명
    "note"     TEXT NULL                     -- 비고 (예: 조직개편 이력 메모)
);

-- 2. 권고 (사참위 원본 권고사항)
CREATE TABLE "REC" (
    "rec_id"     SERIAL PRIMARY KEY,         -- 권고ID
    "category"   VARCHAR(50) NOT NULL,       -- 분야 (가습기살균제/세월호참사/재난및피해지원일반)
    "rec_no"     VARCHAR(20) NOT NULL,       -- 권고번호 (원문 기준, 예: "2-1")
    "content"    TEXT NOT NULL,              -- 권고내용
    "necessity"  TEXT NULL,                  -- 필요성 (마크다운, 각주 포함 가능)
    "source"     VARCHAR(200) NULL           -- 출처 (원본 문서명/페이지)
);

-- 3. 관련조사자료
CREATE TABLE "EVID" (
    "evid_id"  SERIAL PRIMARY KEY,           -- 자료ID
    "code"     VARCHAR(50) NULL,             -- 자료코드 (예: "직가-1")
    "title"    VARCHAR(300) NOT NULL         -- 자료명
);

-- 4. 계정 (팀원 20명 개인별 로그인)
CREATE TABLE "AUTH" (
    "auth_id"       SERIAL PRIMARY KEY,      -- 계정ID
    "auth_name"     VARCHAR(50) NOT NULL,    -- 이름
    "password_hash" VARCHAR(64) NOT NULL     -- SHA-256 해시 (salt 포함 권장)
);

-- 5. 권고-기관 연결 (다대다 관계 해소)
CREATE TABLE "REC_INST" (
    "link_id"  SERIAL PRIMARY KEY,           -- 연결ID
    "rec_id"   INTEGER NOT NULL,             -- 권고ID (FK)
    "inst_id"  INTEGER NOT NULL,             -- 기관ID (FK)
    CONSTRAINT "FK_REC_INST_REC"
        FOREIGN KEY ("rec_id") REFERENCES "REC" ("rec_id"),
    CONSTRAINT "FK_REC_INST_INST"
        FOREIGN KEY ("inst_id") REFERENCES "INST" ("inst_id"),
    CONSTRAINT "UQ_REC_INST" UNIQUE ("rec_id", "inst_id")  -- 같은 권고-기관 조합 중복 방지
);

-- 6. 권고-조사자료 연결 (다대다 관계 해소)
CREATE TABLE "REC_EVID" (
    "link_id"  SERIAL PRIMARY KEY,           -- 연결ID
    "rec_id"   INTEGER NOT NULL,             -- 권고ID (FK)
    "evid_id"  INTEGER NOT NULL,             -- 자료ID (FK)
    CONSTRAINT "FK_REC_EVID_REC"
        FOREIGN KEY ("rec_id") REFERENCES "REC" ("rec_id"),
    CONSTRAINT "FK_REC_EVID_EVID"
        FOREIGN KEY ("evid_id") REFERENCES "EVID" ("evid_id"),
    CONSTRAINT "UQ_REC_EVID" UNIQUE ("rec_id", "evid_id")  -- 같은 권고-자료 조합 중복 방지
);

-- 7. 이행보고 (연도별 이행현황/향후계획)
-- embedding/embedding_model: 벡터 임베딩 기반 정체 탐지용 (core/similarity/ 참고).
-- pgvector 확장 필요 (core/similarity/schema.sql로 별도 적용).
CREATE TABLE "IMPL" (
    "impl_id"         SERIAL PRIMARY KEY,           -- 보고ID
    "link_id"         INTEGER NOT NULL,             -- 연결ID (FK)
    "year"            INTEGER NOT NULL,             -- 연도
    "status"          TEXT NULL,                    -- 이행현황
    "plan"            TEXT NULL,                    -- 향후계획
    "source"          VARCHAR(200) NULL,            -- 출처 (연도별 보고서 페이지)
    "embedding"        vector(768) NULL,             -- status 임베딩 (nomic-embed-text 기준)
    "embedding_model"  VARCHAR(50) NULL,             -- 임베딩을 만든 모델명
    CONSTRAINT "FK_IMPL_REC_INST"
        FOREIGN KEY ("link_id") REFERENCES "REC_INST" ("link_id"),
    CONSTRAINT "UQ_IMPL" UNIQUE ("link_id", "year")  -- 같은 연결의 같은 연도 중복 방지
);

-- 8. 시민 피드백 (이행보고에 대한 문제제기)
-- link_id: 항상 채움 (REC_INST 기준 — "이 기관·이 권고"에 대한 피드백이라는 뜻).
-- impl_id: 특정 연도 보고를 겨냥한 피드백이면 채움, 이행보고 자체가 없는 상태에
--   대한 피드백(예: 국회의장처럼 한 번도 보고 안 한 기관)이면 NULL.
CREATE TABLE "FEEDBACK" (
    "feedback_id"  SERIAL PRIMARY KEY,       -- 피드백ID
    "link_id"      INTEGER NOT NULL,         -- 권고-기관 연결ID (FK)
    "impl_id"      INTEGER NULL,             -- 이행보고ID (FK, 특정 연도 보고 대상일 때만)
    "auth_id"      INTEGER NOT NULL,         -- 작성자 계정ID (FK)
    "content"      TEXT NOT NULL,            -- 문제제기 내용
    "created_at"   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 작성일시
    CONSTRAINT "FK_FEEDBACK_REC_INST"
        FOREIGN KEY ("link_id") REFERENCES "REC_INST" ("link_id"),
    CONSTRAINT "FK_FEEDBACK_IMPL"
        FOREIGN KEY ("impl_id") REFERENCES "IMPL" ("impl_id"),
    CONSTRAINT "FK_FEEDBACK_AUTH"
        FOREIGN KEY ("auth_id") REFERENCES "AUTH" ("auth_id")
);

-- 8-1. 피드백 근거자료 링크 (피드백 1개에 여러 개 가능)
CREATE TABLE "FEEDBACK_EVIDENCE" (
    "evidence_id"  SERIAL PRIMARY KEY,       -- 근거링크ID
    "feedback_id"  INTEGER NOT NULL,         -- 피드백ID (FK)
    "url"          VARCHAR(300) NOT NULL,    -- 근거자료 링크
    CONSTRAINT "FK_FEEDBACK_EVIDENCE_FEEDBACK"
        FOREIGN KEY ("feedback_id") REFERENCES "FEEDBACK" ("feedback_id") ON DELETE CASCADE
);

-- 9. 용어사전
CREATE TABLE "TERM" (
    "term_id"       SERIAL PRIMARY KEY,      -- 용어ID
    "term"          VARCHAR(100) NOT NULL,   -- 용어
    "definition"    TEXT NOT NULL,           -- 사전적/일반적 의미
    "context"       TEXT NULL,               -- 이 프로젝트 맥락에서의 의미
    "category"      VARCHAR(50) NULL,        -- 사회적개념/법률용어/기관약칭 등
    "created_by"    INTEGER NOT NULL,        -- 작성자 계정ID (FK)
    "created_at"    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updated_by"    INTEGER NULL,            -- 수정자 계정ID (FK)
    "updated_at"    TIMESTAMP NULL,
    "is_deleted"    BOOLEAN DEFAULT FALSE,   -- 실제 삭제 대신 숨김 처리
    CONSTRAINT "FK_TERM_CREATED_BY" FOREIGN KEY ("created_by") REFERENCES "AUTH" ("auth_id"),
    CONSTRAINT "FK_TERM_UPDATED_BY" FOREIGN KEY ("updated_by") REFERENCES "AUTH" ("auth_id")
);

-- ============================================
-- 조회 편의를 위한 인덱스
-- ============================================
CREATE INDEX "idx_rec_no" ON "REC" ("rec_no");
CREATE INDEX "idx_impl_year" ON "IMPL" ("year");
CREATE INDEX "idx_feedback_evidence_feedback" ON "FEEDBACK_EVIDENCE" ("feedback_id");
-- status는 마크다운 풀텍스트라 btree 튜플 크기 제한을 넘을 수 있음.
-- "이행현황 완전동일 여부(등호 비교)" 조회만 지원하면 되므로 HASH 인덱스 사용.
CREATE INDEX "idx_impl_status" ON "IMPL" USING HASH ("status");
CREATE INDEX "idx_feedback_impl" ON "FEEDBACK" ("impl_id");
CREATE INDEX "idx_feedback_link" ON "FEEDBACK" ("link_id");
