# Ollama 설정 가이드

로컬 GPU(RTX 4090, 24GB VRAM)에서 Ollama로 LLM을 구동하기 위한 설정 정리.
RAG 파이프라인의 답변 생성, 질문 분해(파라미터 추출) 등에 사용.

## 설치 (WSL/Linux 기준)

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

설치 스크립트가 NVIDIA GPU를 자동 감지해 CUDA 연동까지 처리함.

```bash
ollama --version
```

## 모델 선택

### 후보 모델

| 모델 | 크기 | 비고 |
|---|---|---|
| Qwen2.5 | 14B | 성능 준수하나 한국어 응답에 중국어가 섞이는 문제 발생 |
| EXAONE (LG AI연구원) | 7.8B | 한국어 특화, 법률/행정 도메인 문서에 상대적으로 적합 |

```bash
ollama pull qwen2.5:14b
ollama pull exaone3.5:7.8b
```

### 알려진 문제: Qwen 계열의 중국어 혼입

Qwen 모델은 학습 데이터에서 중국어 비중이 높아, 특히 다음 상황에서 응답에 중국어가
섞여 나올 수 있음:
- 모델 크기가 작을수록(14B 등 중간 크기) 언어 전환 문제가 두드러짐
- Ollama 기본 pull은 보통 Q4 양자화라, 양자화 수준이 낮을수록 언어 일관성 저하
- 짧거나 애매한 프롬프트에서 기본 언어로 회귀하는 경향

**대응 방법**:
1. 시스템 프롬프트에 "반드시 한국어로만 답변, 중국어/영어 섞지 말 것" 명시
2. `temperature`를 0.3~0.5로 낮춤 (RAG 용도에는 어차피 낮은 값이 적합)
3. Q4 대신 Q8 양자화 버전 시도: `ollama pull qwen2.5:14b-instruct-q8_0`
4. EXAONE 등 한국어 특화 모델과 비교 테스트

## 파이썬에서 API 호출

### 기본 (generate 엔드포인트)

```python
import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen2.5:14b",
        "prompt": "사회적참사 특별법의 목적이 뭐야?",
        "stream": False,
        "options": {"temperature": 0.3}
    }
)
print(response.json()["response"])
```

### 시스템 프롬프트 포함 (chat 엔드포인트 권장)

```python
import requests

response = requests.post(
    "http://localhost:11434/api/chat",
    json={
        "model": "qwen2.5:14b",
        "messages": [
            {"role": "system", "content": "당신은 반드시 한국어로만 답변합니다. 어떤 상황에서도 중국어나 영어를 섞지 마세요."},
            {"role": "user", "content": "사회적참사 특별법의 목적이 뭐야?"}
        ],
        "stream": False,
        "options": {"temperature": 0.3}
    }
)
print(response.json()["message"]["content"])
```

## 동시 접속 대응 (팀원 약 20명 사용 가정)

Ollama 기본 설정은 요청을 순차 처리하는 경향이 있어, 여러 사용자가 몰리면 대기시간이
길어질 수 있음. 환경변수로 병렬 처리 조정 가능.

```bash
export OLLAMA_NUM_PARALLEL=4        # 동시 처리 요청 수
export OLLAMA_MAX_LOADED_MODELS=1   # 모델 하나만 사용하므로 1로 고정
export OLLAMA_MAX_QUEUE=20          # 대기열 최대 크기 (0=무제한)
```

**영구 적용 (systemd 서비스 환경변수로 등록)**:
```bash
sudo systemctl edit ollama
```
아래 내용 추가:
```ini
[Service]
Environment="OLLAMA_NUM_PARALLEL=4"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_MAX_QUEUE=20"
```
적용:
```bash
sudo systemctl restart ollama
```

**VRAM 참고치**: 14B 모델(Q4 양자화) 1개 로드 시 약 9~10GB, `NUM_PARALLEL=4`
설정 시 병렬 컨텍스트로 4~6GB 추가 소요 → 총 14~16GB 수준. RTX 4090(24GB)에서
4 정도는 여유 있게 감당 가능. 실제 부하는 `nvidia-smi`로 확인 권장.

```bash
nvidia-smi --query-gpu=power.draw,memory.used --format=csv -l 5
```

## Claude API와의 역할 분담 (하이브리드 전략)

로컬 Ollama와 Claude API를 용도별로 나눠 쓰는 것을 권장:

| 용도 | 사용 모델 | 이유 |
|---|---|---|
| 단순 조회, 요약, 반복 작업 | 로컬 Ollama (Qwen/EXAONE) | 비용 없음, 데이터 외부 미전송 |
| 정교한 추론 필요 (예: 검증 항목 자동 분해) | Claude API | 품질 차이 크고, 사용 빈도 낮아 비용 부담 적음 |

Claude API 호출 예시:
```python
import anthropic

client = anthropic.Anthropic(api_key="...")
message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1000,
    messages=[{"role": "user", "content": prompt}]
)
print(message.content[0].text)
```

**민감정보 고려**: 세월호/가습기살균제 참사 피해자 관련 데이터를 다루는 프로젝트라,
외부 API로 전송하는 것에 대한 부담이 있을 수 있음. 기본은 로컬 처리, 필요한 경우만
선별적으로 API 사용하는 방향으로 설계.

## LLM을 통한 SQL 생성 (text-to-SQL) 패턴

사용자의 자연어 질문을 구조화 DB 쿼리로 변환할 때, 스키마 정보를 프롬프트에 텍스트로
포함시켜 LLM이 참고하도록 함. LLM이 DB에 직접 연결되는 것이 아니라, 스키마 설명 +
질문을 프롬프트로 합쳐 전달하고, LLM이 생성한 SQL 문자열을 애플리케이션이 실행하는 구조.

```python
schema_info = """
CREATE TABLE REC (rec_id, category, rec_no, content, necessity, source);
CREATE TABLE INST (inst_id, name, note);
CREATE TABLE REC_INST (link_id, rec_id, inst_id);
CREATE TABLE EVID (evid_id, code, title);
CREATE TABLE REC_EVID (link_id, rec_id, evid_id);
CREATE TABLE IMPL (impl_id, link_id, year, status, plan, source);
"""

prompt = f"""
{schema_info}

위 스키마를 참고해서, 다음 질문에 답하는 PostgreSQL 쿼리를 작성해줘.
질문: {user_question}

SQL 쿼리만 출력하고 다른 설명은 하지 마.
"""
```

생성된 SQL은 애플리케이션이 PostgreSQL에 실행하고, 결과를 다시 사람이 읽기 좋게
정리하는 후처리 단계를 거침.

## 관련 문서

- 전체 스키마: `schema.md`
- 이 프로젝트의 RAG 아키텍처 결정 배경: `design-decisions.md` 중
  "순수 RAG가 아니라 구조화 DB + 벡터검색 하이브리드로 간 이유" 참고
