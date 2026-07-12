-- 정체 탐지 방식 2: 벡터 임베딩 거리 (docs/design-decisions.md 참고).
-- REC_INST 링크의 연도 N/N+1 status가 문구는 다르지만 의미상 거의 동일한
-- "의심 정황"을 코사인 거리로 탐지한다. 필요한 연산이 "링크 내 인접 연도 1:1 비교"뿐이라
-- (많은 벡터 중 최근접 이웃을 찾는 문제가 아님), Chroma 같은 별도 벡터DB 없이
-- 이미 있는 구조화 DB(Postgres) 안에서 pgvector로 처리한다.
--
-- 새 볼륨으로 DB를 처음 띄울 때 한 번 실행하면 된다:
--   docker compose exec -T db psql -U rec_admin -d rec_proj < core/similarity/schema.sql

CREATE EXTENSION IF NOT EXISTS vector;

-- nomic-embed-text 임베딩 차원(768)에 맞춤. 다른 임베딩 모델로 바꾸면 차원이 달라질 수
-- 있으니 이 컬럼 자체를 다시 만들어야 한다.
-- (bge-m3, multilingual-e5-large 둘 다 시도했으나 이 도메인 텍스트에선 재탕/실질변화
-- 구분력이 nomic-embed-text보다 떨어져서 복귀했다 — 관공서 문체 특성상 유사도가 전반적으로
-- 높게 뭉치는 경향이 있어 임계값 기반 분리가 어려움.)
ALTER TABLE "IMPL" ADD COLUMN IF NOT EXISTS "embedding" vector(768);

-- 어떤 모델로 만든 벡터인지 기록. 모델을 바꾸면 벡터 공간이 달라져 이전 임베딩과
-- 비교가 불가능해지므로, core/similarity/backfill.py가 이 값을 보고 재생성이
-- 필요한 행을 가려낸다 (조용히 잘못된 비교를 하지 않도록).
ALTER TABLE "IMPL" ADD COLUMN IF NOT EXISTS "embedding_model" VARCHAR(50);
