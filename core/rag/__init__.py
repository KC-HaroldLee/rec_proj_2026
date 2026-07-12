# 자연어 질문 해석기: 질문 -> SQL 생성 -> 실행 -> 자연어 답변.
# 진입점은 qa.answer_question(). docs/design-decisions.md, docs/project-overview.md의
# "왜 순수 RAG가 아닌가" 참고.
# 벡터 유사도 기반 정체 탐지(의미상 재탕 탐지)는 core/similarity/ 참고 — 별도 모듈.
