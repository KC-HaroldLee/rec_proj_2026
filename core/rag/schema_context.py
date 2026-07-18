"""text-to-SQL 프롬프트에 그대로 끼워넣는 스키마 설명.

AUTH 테이블은 의도적으로 뺐다 — LLM이 애초에 그 테이블의 존재를 모르게 하는 게
sql_guard.py의 문자열 검사나 DB 롤 권한보다 먼저 걸리는 가장 단순한 방어선이다.

작은 로컬 모델(예: llama3.2:1b)이 REC/INST/IMPL을 매번 정확히 3-way JOIN하지 못하고
존재하지 않는 컬럼(INST.rec_id 등)을 지어내는 문제가 실측으로 확인됐다. core/rag/
views.sql로 평탄화 뷰(rec_inst_flat, impl_flat)를 만들어서 JOIN을 아예 안 해도 되게
했다. **주의**: 스키마 설명에 few-shot 예시나 긴 부연설명을 추가했더니 이 모델이
질문을 되풀이하며 여러 개 답을 만드는 등 오히려 더 무너지는 걸 실측으로 확인함 —
이 프롬프트는 짧게 유지할 것. 원본 테이블 나열도 최소한만 남긴다.
"""

SCHEMA_CONTEXT = """
CREATE VIEW rec_inst_flat (rec_id, rec_no, category, content, necessity, link_id, inst_id, inst_name);
-- 권고 x 대상기관 (JOIN 미리 처리됨). 기관 관련 질문엔 이걸 써라.

CREATE VIEW impl_flat (impl_id, year, status, plan, rec_id, rec_no, category, content, link_id, inst_id, inst_name);
-- 이행현황(IMPL) x 권고 x 기관 (JOIN 미리 처리됨). 이행현황/연도 관련 질문엔 이걸 써라.

CREATE TABLE "REC" (rec_id, category, rec_no, content, necessity, source);
CREATE TABLE "INST" (inst_id, name, note);
CREATE TABLE "EVID" (evid_id, code, title);
CREATE TABLE "REC_EVID" (link_id, rec_id, evid_id);
CREATE TABLE "IMPL" (impl_id, link_id, year, status, plan, source);
CREATE TABLE "FEEDBACK" (feedback_id, link_id, impl_id, auth_id, content, created_at);
CREATE TABLE "FEEDBACK_EVIDENCE" (evidence_id, feedback_id, url);
CREATE TABLE "TERM" (term_id, term, definition, context, category);
"""
