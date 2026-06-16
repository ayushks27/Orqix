FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./shared /app/shared
COPY ./services/workflow /app/services/workflow

ENV PYTHONPATH=/app

CMD ["uvicorn", "services.workflow.main:app", "--host", "0.0.0.0", "--port", "8002"]
