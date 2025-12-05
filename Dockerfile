FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY knowledge_base/ ./knowledge_base/
COPY tests/ ./tests/

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=local
ENV OLLAMA_HOST=http://ollama:11434

CMD ["python", "-m", "src.cli", "--help"]
