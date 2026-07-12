"""IMPL.status 임베딩을 계산해서 저장하는 배치 스크립트.

상태 텍스트는 있는데 임베딩이 없거나 다른 모델로 만들어진 행만 골라서 처리한다
(schema.sql의 embedding_model 컬럼 참고 — 임베딩 모델을 바꾸면 벡터 공간이 달라져
이전 벡터와 비교가 불가능해지므로, 재생성이 필요한 행을 구분해야 한다).

사용법: python3 -m core.similarity.backfill
"""
import sys

from dotenv import load_dotenv

load_dotenv()

from app.db import get_conn
from core.similarity.embed import EMBED_MODEL, embed


def _to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vec) + "]"


def main():
    with get_conn() as conn:
        rows = conn.execute(
            '''
            SELECT impl_id, status FROM "IMPL"
            WHERE status IS NOT NULL
              AND (embedding IS NULL OR embedding_model IS DISTINCT FROM %s)
            ''',
            (EMBED_MODEL,),
        ).fetchall()

        print(f"{len(rows)}건 임베딩 생성 중 (model={EMBED_MODEL})...", file=sys.stderr)
        for i, row in enumerate(rows, start=1):
            vec = embed(row["status"])
            conn.execute(
                'UPDATE "IMPL" SET embedding = %s::vector, embedding_model = %s WHERE impl_id = %s',
                (_to_pgvector(vec), EMBED_MODEL, row["impl_id"]),
            )
            if i % 20 == 0 or i == len(rows):
                print(f"  {i}/{len(rows)}", file=sys.stderr)

    print("완료", file=sys.stderr)


if __name__ == "__main__":
    main()
