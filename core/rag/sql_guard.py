"""LLM이 만든 SQL을 실행하기 전 1차 검증.

이게 유일한 방어선은 아니다 — 실제 실행은 SELECT 권한만 가진 별도 DB 롤
(rec_readonly, AUTH 테이블은 GRANT 대상에서 제외, readonly_role.sql 참고)로
하기 때문에, 여기를 뚫려도 DB 권한 수준에서 다시 막힌다. 이 검증은 그 전에
빠르게 실패해서 사용자에게 명확한 에러를 보여주기 위한 용도.
"""
import re

_CODE_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

_DANGEROUS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CREATE|EXEC|EXECUTE|"
    r"CALL|COPY|VACUUM|ATTACH|MERGE|REPLACE|INTO|LOCK|LISTEN|NOTIFY|SET|RESET|"
    r"PG_READ_FILE|PG_LS_DIR|DBLINK)\b",
    re.IGNORECASE,
)
_AUTH_REF = re.compile(r'\bAUTH\b', re.IGNORECASE)


class UnsafeSQLError(ValueError):
    pass


def extract_sql(llm_output: str) -> str:
    """LLM 응답에서 ```sql ... ``` 코드펜스가 있으면 벗겨내고, 없으면 그대로 반환."""
    m = _CODE_FENCE.search(llm_output)
    return (m.group(1) if m else llm_output).strip()


def validate_readonly_select(sql: str) -> str:
    sql = sql.strip().rstrip(";").strip()

    if not sql:
        raise UnsafeSQLError("빈 SQL이 생성되었습니다.")
    if ";" in sql:
        raise UnsafeSQLError("한 번에 하나의 SQL 문장만 허용됩니다.")
    if not re.match(r"^(SELECT|WITH)\b", sql, re.IGNORECASE):
        raise UnsafeSQLError("SELECT/WITH 조회 쿼리만 허용됩니다.")
    if _DANGEROUS.search(sql):
        raise UnsafeSQLError("허용되지 않는 SQL 키워드가 포함되어 있습니다.")
    if _AUTH_REF.search(sql):
        raise UnsafeSQLError("AUTH 테이블은 조회할 수 없습니다.")

    return sql
