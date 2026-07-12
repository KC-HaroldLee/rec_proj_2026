"""Ollama HTTP API 얇은 래퍼. docs/ollama-guide.md의 chat 엔드포인트 패턴을 따른다."""
import os

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "exaone3.5:7.8b")

SYSTEM_PROMPT = (
    "당신은 사참위 권고 이행 모니터링 시스템의 질문 해석기입니다. "
    "반드시 한국어로만 답변하세요. 어떤 상황에서도 중국어나 영어를 섞지 마세요."
)


def chat(user_prompt: str, *, temperature: float = 0.3) -> str:
    resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": CHAT_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]
