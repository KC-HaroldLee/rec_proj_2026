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