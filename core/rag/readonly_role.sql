-- text-to-SQL이 LLM이 만든 SQL을 그대로 실행하는 구조라서(docs/ollama-guide.md 패턴),
-- 문자열 검증(core/rag/sql_guard.py)만으로는 우회 가능성을 완전히 배제할 수 없다.
-- 실제 실행 권한 자체를 SELECT-only로 제한하고, AUTH(비밀번호 해시)는 아예 GRANT하지
-- 않는 것으로 최종 방어선을 둔다.
--
-- 비밀번호는 이 파일에 평문으로 넣지 않는다 (git에 커밋되는 파일이라서) — psql 변수로
-- .env의 RAG_DB_PASSWORD를 넘겨서 실행:
--   docker compose exec -T db psql -U rec_admin -d rec_proj \
--     -v rag_db_password="$RAG_DB_PASSWORD" < core/rag/readonly_role.sql
--
-- 이미 만들어진 롤에 다시 돌려도 안전(멱등) — 존재하면 건너뛰고 비밀번호만 갱신.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rec_readonly') THEN
        CREATE ROLE rec_readonly LOGIN;
    END IF;
END
$$;

ALTER ROLE rec_readonly PASSWORD :'rag_db_password';

GRANT CONNECT ON DATABASE rec_proj TO rec_readonly;
GRANT USAGE ON SCHEMA public TO rec_readonly;

-- AUTH는 의도적으로 제외 (password_hash 보호).
GRANT SELECT ON
    "REC", "INST", "REC_INST", "EVID", "REC_EVID", "IMPL", "FEEDBACK", "FEEDBACK_EVIDENCE", "TERM"
TO rec_readonly;

ALTER ROLE rec_readonly SET default_transaction_read_only = on;
ALTER ROLE rec_readonly SET statement_timeout = '5s';
