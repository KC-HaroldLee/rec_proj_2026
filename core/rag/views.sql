-- text-to-SQL용 평탄화 뷰. 작은 로컬 모델(예: llama3.2:1b)이 REC/INST/IMPL을
-- 매번 정확히 3-way JOIN하지 못하고 존재하지 않는 컬럼(INST.rec_id 등)을
-- 지어내는 문제가 실측으로 확인됐다 — 자주 쓰는 조합을 뷰로 미리 풀어둬서
-- LLM이 JOIN 자체를 안 만들어도 되게 하는 게 목적 (core/rag/schema_context.py 참고).
--
-- rec_readonly 롤이 이미 있어야 한다 (core/rag/readonly_role.sql을 먼저 실행할 것).
-- 새 볼륨으로 DB를 처음 띄울 때 한 번 실행하면 된다:
--   docker compose exec -T db psql -U rec_admin -d rec_proj < core/rag/views.sql

CREATE OR REPLACE VIEW rec_inst_flat AS
SELECT
    r.rec_id, r.rec_no, r.category, r.content, r.necessity,
    ri.link_id,
    i.inst_id, i.name AS inst_name
FROM "REC" r
JOIN "REC_INST" ri ON r.rec_id = ri.rec_id
JOIN "INST" i ON ri.inst_id = i.inst_id;

CREATE OR REPLACE VIEW impl_flat AS
SELECT
    im.impl_id, im.year, im.status, im.plan, im.source AS impl_source,
    rif.rec_id, rif.rec_no, rif.category, rif.content,
    rif.link_id, rif.inst_id, rif.inst_name
FROM "IMPL" im
JOIN rec_inst_flat rif ON im.link_id = rif.link_id;

GRANT SELECT ON rec_inst_flat, impl_flat TO rec_readonly;
