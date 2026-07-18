FROM python:3.12-slim

WORKDIR /app

# psycopg[binary]는 wheel로 오지만 혹시 모를 빌드 대비 최소 툴체인만 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY core ./core

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
