FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./shared /app/shared
COPY ./services/dataset /app/services/dataset

ENV PYTHONPATH=/app

CMD ["uvicorn", "services.dataset.main:app", "--host", "0.0.0.0", "--port", "8004"]
