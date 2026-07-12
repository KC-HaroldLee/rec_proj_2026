"""자연어 질문 -> SQL 생성 -> 실행 -> 자연어 답변, 2단계 파이프라인.

docs/ollama-guide.md의 text-to-SQL 패턴을 그대로 따른다. 벡터 유사도 기반 정체 탐지
("의미상 비슷한 재탕" 탐지, docs/project-overview.md "핵심 가치: 정체 탐지"의 2번)는
이 모듈이 아니라 core/similarity/에 별도로 있다.
"""
import json

from core.rag.db import get_readonly_conn
from core.rag.ollama_client import chat
from core.rag.schema_context import SCHEMA_CONTEXT
from core.rag.sql_guard import UnsafeSQLError, extract_sql, validate_readonly_select

MAX_ROWS = 200
_MAX_FIELD_CHARS = 300  # 답변 생성 프롬프트에 넣기 전 긴 텍스트(content 등) 자르는 길이

SQL_PROMPT_TEMPLATE = """\
아래는 PostgreSQL 데이터베이스의 테이블 구조다. 테이블명은 모두 대문자이고
큰따옴표로 감싸야 하는 quoted identifier다 (예: "REC", "REC_INST").
따옴표 없이 소문자로 쓰면(rec 등) 존재하지 않는 테이블로 취급되어 오류가 난다.
{schema}
위 스키마를 참고해서, 다음 질문에 답하는 PostgreSQL 조회 쿼리를 작성해줘.
테이블명은 반드시 스키마에 적힌 그대로 큰따옴표를 포함해서 써라 (FROM "REC" 형태).
질문이 특정 권고나 기관에 대한 것이면, 사용자가 원본을 바로 확인할 수 있도록
결과에 rec_id(그리고 있으면 inst_id)를 같이 SELECT해줘. 단순 개수·집계 질문이면
안 넣어도 된다.
반드시 SELECT 또는 WITH로 시작하는 조회 쿼리 하나만 작성하고, 세미콜론이나 다른 설명 없이
SQL 쿼리만 출력해.

질문: {question}
"""

ANSWER_PROMPT_TEMPLATE = """\
사용자가 다음 질문을 했다: {question}

이 질문에 답하기 위해 실행한 SQL 조회 결과는 다음과 같다 (JSON 배열):
{rows_json}

이 결과만 근거로 사용자 질문에 대한 답을 한국어로 자연스럽게 설명해줘.
결과 배열이 비어 있으면 "관련 데이터를 찾지 못했습니다"라고 답해.
결과에 없는 숫자나 사실을 지어내지 마.
"""


class RagError(Exception):
    """사용자에게 그대로 보여줘도 되는 실패 메시지."""


def _truncate_for_prompt(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        trimmed = {}
        for k, v in row.items():
            if isinstance(v, str) and len(v) > _MAX_FIELD_CHARS:
                v = v[:_MAX_FIELD_CHARS] + "..."
            trimmed[k] = v
        out.append(trimmed)
    return out


def answer_question(question: str) -> dict:
    sql_prompt = SQL_PROMPT_TEMPLATE.format(schema=SCHEMA_CONTEXT, question=question)
    try:
        raw = chat(sql_prompt)
    except Exception as e:
        raise RagError("Ollama에 연결하지 못했습니다. 로컬 LLM이 켜져 있는지 확인해주세요.") from e

    sql = extract_sql(raw)
    try:
        sql = validate_readonly_select(sql)
    except UnsafeSQLError as e:
        raise RagError(f"안전하지 않은 쿼리라 실행을 거부했습니다: {e}") from e

    try:
        with get_readonly_conn() as conn:
            rows = conn.execute(sql).fetchmany(MAX_ROWS)
    except Exception as e:
        # 원인은 대부분 LLM이 생성한 SQL 자체가 질문과 안 맞는 경우(예: 데이터 조회와
        # 무관한 인사말)라 원본 Postgres 에러를 그대로 보여줘봐야 사용자에게 의미가 없다.
        raise RagError("질문을 이해하지 못했어요. 다르게 표현해서 다시 물어봐 주세요.") from e

    rows_json = json.dumps(_truncate_for_prompt(rows), ensure_ascii=False, default=str)
    answer_prompt = ANSWER_PROMPT_TEMPLATE.format(question=question, rows_json=rows_json)
    try:
        answer = chat(answer_prompt)
    except Exception as e:
        raise RagError("Ollama에 연결하지 못했습니다. 로컬 LLM이 켜져 있는지 확인해주세요.") from e

    return {"sql": sql, "rows": rows, "answer": answer}
