FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY tokreducer/ ./tokreducer/

RUN pip install --no-cache-dir ".[api]"

EXPOSE 8080

CMD ["uvicorn", "tokreducer.api.server:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]
