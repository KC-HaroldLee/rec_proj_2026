"""text-to-SQL 실행 전용 커넥션. app/db.py(rec_admin)와는 별도로,
SELECT만 가능하고 AUTH는 아예 못 보는 rec_readonly 롤을 쓴다."""
import os

import psycopg
from psycopg.rows import dict_row


def get_readonly_conn() -> psycopg.Connection:
    conn = psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["RAG_DB_USER"],
        password=os.environ["RAG_DB_PASSWORD"],
        row_factory=dict_row,
    )
    conn.read_only = True
    return conn
