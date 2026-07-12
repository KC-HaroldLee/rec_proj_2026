"""
임베딩 기반 '실질적 재탕' 탐지 프로토타입.

SQL 완전일치(status = status)로는 못 잡는 근사-재탕 사례를 임베딩 코사인 유사도로
잡을 수 있는지 검증한다. 비교군:
  - A: rec 2-2 / 국정원장 2023년 status
  - B: rec 2-2 / 국정원장 2024년 status (A와 거의 동일하지만 완전일치는 아님 — 괄호 문자만 다름)
  - C: 서로 다른 권고의 status (네거티브 컨트롤 — 명백히 다른 내용)

사용법: python3 scripts/test_embedding_similarity.py
(Ollama가 로컬에서 실행 중이어야 하고, nomic-embed-text 모델이 pull되어 있어야 함)
"""
import subprocess
import json
import numpy as np
import requests

OLLAMA_URL = "http://localhost:11434/api/embed"
MODEL = "nomic-embed-text"


def fetch_status(rec_no, inst_name, year):
    sql = f"""
    SELECT a.status FROM "IMPL" a
    JOIN "REC_INST" ri ON a.link_id = ri.link_id
    JOIN "REC" r ON ri.rec_id = r.rec_id
    JOIN "INST" i ON ri.inst_id = i.inst_id
    WHERE r.rec_no = '{rec_no}' AND i.name = '{inst_name}' AND a.year = {year};
    """
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "psql", "-U", "rec_admin", "-d", "rec_proj",
         "-t", "-A", "-c", sql],
        cwd="/home/kk4ever/workspace/rec_proj",
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def embed(text):
    resp = requests.post(OLLAMA_URL, json={"model": MODEL, "input": text})
    resp.raise_for_status()
    return np.array(resp.json()["embeddings"][0])


def cosine_sim(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def main():
    a_text = fetch_status("2-2", "국정원장", 2023)
    b_text = fetch_status("2-2", "국정원장", 2024)
    c_text = fetch_status("1-1", "환경부 장관", 2024)  # 완전히 다른 내용 (네거티브 컨트롤)

    print("=== A (2-2/국정원장/2023) ===")
    print(a_text[:150])
    print("\n=== B (2-2/국정원장/2024) ===")
    print(b_text[:150])
    print("\n=== C (1-1/환경부장관/2024, 네거티브 컨트롤) ===")
    print(c_text[:150])

    print("\nSQL 완전일치(A == B)?", a_text == b_text)

    vec_a = embed(a_text)
    vec_b = embed(b_text)
    vec_c = embed(c_text)

    print("\n--- 코사인 유사도 ---")
    print(f"A vs B (근사-재탕 의심): {cosine_sim(vec_a, vec_b):.4f}")
    print(f"A vs C (네거티브 컨트롤): {cosine_sim(vec_a, vec_c):.4f}")


if __name__ == "__main__":
    main()
