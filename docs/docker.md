# PostgreSQL / Docker 셋업 메모

도커 설치 완료 후 진행할 작업을 정리한 문서. `schema.md`(테이블 정의), `design-decisions.md`(왜 이렇게 설계했는지)와 같이 참고.

## 1. Docker 환경 (완료)

- `docker-compose.yml`: postgres:16 이미지 + 볼륨 마운트(데이터 영속화) + 5432 포트 + `.env`(`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`)
- 비밀번호는 `.env` 파일로 분리, `.gitignore`에 포함 (커밋 금지)
- `docker compose up -d`로 기동, `docker compose exec db psql -U rec_admin -d rec_proj`로 접속

## 2. 스키마 적용 (완료)

`db-schema.sql`을 `schema.md` 기준으로 최신화 완료:
- `REC.necessity` 컬럼 추가
- `EVID`, `REC_EVID`, `TERM` 테이블 추가

`docker compose exec -T db psql -U rec_admin -d rec_proj < db-schema.sql`로 적용, 9개 테이블 생성 확인됨.

## 3. 데이터 적재 순서

FK 의존성 때문에 순서가 중요함:

1. `INST`, `EVID`, `AUTH` — 의존성 없음, SERIAL로 id 자동생성
2. `REC` — 의존성 없음
3. `REC_INST` — `data/parsed/rec/REC_INST.csv`의 `rec_no`/`inst_name`을 각각 `REC.rec_no`, `INST.name`과 조인해서 실제 `rec_id`/`inst_id`로 변환 후 insert. CSV 자체엔 id가 없으므로 자연키 매칭이 필요 (staging 테이블 하나 거치는 방식 권장)
4. `REC_EVID` — 위와 같은 방식이지만, 이건 아직 매핑 데이터 자체를 안 뽑음 (나중 작업)
5. `IMPL`, `FEEDBACK`, `TERM` — 아직 원본 데이터 없음, 스키마만 존재

## 4. 그 외 확인할 것

- CSV 인코딩이 전부 UTF-8인지 확인 (`\copy` 사용 시 인코딩 명시 필요할 수 있음)
- `REC.csv`의 `content`/`necessity` 필드에 개행·따옴표 포함된 마크다운이 있어서, `\copy`보다 Python(psycopg2) 스크립트로 적재하는 게 안전함

## 5. 알려진 데이터 이슈

- `data/parsed/rec/INST.csv`: 원래 "해양경찰청장" 기관이 누락되어 있었음 → 확인 후 추가 완료
- `data/parsed/rec/REC_INST.csv`: `REC_2022.pdf` 제2장(권고목록) 표에서 좌표 기반으로 파싱해 생성. 80개 권고 전체에 최소 1개 이상 기관 매핑 확인됨 (최대 9개, rec_no `2-2`)
- `REC_EVID` 매핑 데이터는 아직 미작업 — 필요 시 `EVID.csv`와 원문 대조 작업 별도 진행
