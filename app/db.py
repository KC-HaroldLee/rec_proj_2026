"""DB 커넥션 헬퍼. 요청당 커넥션 하나를 열고 닫는 방식.

TODO: 20명 동시접속 트래픽이 실제로 문제가 되면 psycopg_pool로 교체.
"""
import os

import psycopg
from psycopg.rows import dict_row


def get_conn() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        row_factory=dict_row,
    )
