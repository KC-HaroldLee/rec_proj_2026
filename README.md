# 사참위 권고 이행 모니터링

사참위(사회적참사특별조사위원회) 권고사항의 이행 여부를 팀원들이 함께 추적·검증하는
내부 도구. 왜 만드는지, 핵심 가치는 `docs/project-overview.md` 참고.

## git clone 이후 처음 세팅

```bash
# 1. 파이썬 환경
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. .env 만들기 (git에는 없음 — 시크릿이라 gitignore 대상)
cp .env.example .env   # 없으면 아래 "필요한 값" 참고해서 직접 작성
```

**.env에 필요한 값** (예시, 전부 새로 만들어도 됨):
```
POSTGRES_USER=rec_admin
POSTGRES_PASSWORD=<아무 값>
POSTGRES_DB=rec_proj
POSTGRES_PORT=5432
POSTGRES_HOST=localhost

SESSION_SECRET=<python3 -c "import secrets; print(secrets.token_hex(32))">

RAG_DB_USER=rec_readonly
RAG_DB_PASSWORD=<python3 -c "import secrets; print(secrets.token_hex(24))">

OLLAMA_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=<사양에 맞는 모델, 아래 참고>
```

```bash
# 3. DB 띄우기 (pgvector 포함 이미지)
docker compose up -d db

# 4. 스키마/롤/확장/뷰 적용 (새 볼륨일 때 1회)
docker compose exec -T db psql -U rec_admin -d rec_proj < db-schema.sql
docker compose exec -T db psql -U rec_admin -d rec_proj \
  -v rag_db_password="$RAG_DB_PASSWORD" < core/rag/readonly_role.sql
docker compose exec -T db psql -U rec_admin -d rec_proj < core/rag/views.sql
docker compose exec -T db psql -U rec_admin -d rec_proj < core/similarity/schema.sql

# 5. 데이터 적재 (이미 파싱된 data/parsed/rec/*.csv, impl_*.json 사용)
python3 scripts/load_initial.py | docker compose exec -T db psql -U rec_admin -d rec_proj -v ON_ERROR_STOP=1
python3 scripts/load_impl.py data/parsed/rec/impl_2023_raw.json data/parsed/rec/impl_2024_raw.json data/parsed/rec/impl_2025_raw.json \
  | docker compose exec -T db psql -U rec_admin -d rec_proj -v ON_ERROR_STOP=1

# 6. 임베딩 생성 (Ollama 켜져 있어야 함, nomic-embed-text 필요)
ollama pull nomic-embed-text
python3 -m core.similarity.backfill

# 7. Ollama 채팅 모델 (자연어 검색용)
ollama pull exaone3.5:7.8b   # 원래 추천 모델 (docs/ollama-guide.md 참고)
# VRAM이 부족하면 더 가벼운 모델로 (예: llama3.2:1b) — .env의 OLLAMA_CHAT_MODEL도 맞출 것

# 8. 로그인 계정 최소 1개 만들기 (관리자가 미리 발급하는 구조, 회원가입 없음)
python3 -c "import hashlib; print(hashlib.sha256(b'원하는비번').hexdigest())"
# 나온 해시로:
docker compose exec -T db psql -U rec_admin -d rec_proj \
  -c "INSERT INTO \"AUTH\" (auth_name, password_hash) VALUES ('이름', '<위 해시>');"

# 9. 서버 실행
uvicorn app.main:app --reload
```
`http://localhost:8000` 접속 후 8번에서 만든 계정으로 로그인.

## 이미 만들어둔 DB 볼륨을 그대로 옮겨오는 경우

위 4~8번(스키마/데이터 적재)을 건너뛰고, `docs/PROGRESS.md`의 "DB 데이터" 항목대로
`rec_proj_pgdata` 볼륨을 복원한 뒤 3번(`docker compose up -d db`)만 하면 된다.

## 문서 지도

| 문서 | 언제 보면 되는지 |
|---|---|
| `docs/PROGRESS.md` | **PC를 옮기거나 오래 쉬었다 다시 시작할 때 먼저 읽을 것** — 시간순 진행 로그 + 뭘 다시 해야 하는지 체크리스트 |
| `docs/project-overview.md` | 이 프로젝트가 왜 존재하는지, 핵심 가치 |
| `docs/design-decisions.md` | 왜 이렇게 설계했는지 상세 근거, 아직 미결정인 것들 |
| `docs/schema.md` / `db-schema.sql` | DB 테이블 구조 |
| `docs/screen-design.md` | 화면 구성, 완성된 화면 목록 |
| `docs/ollama-guide.md` | 로컬 LLM 설정, 모델 선택 |
| `core/parse/data-parsing-rules.md` | PDF → 구조화 데이터 파싱 규칙 |
| `docs/features-backlog.md` | 아직 안 만든 기능 아이디어 |
