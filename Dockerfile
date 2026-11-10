# AgenteVFR — app (FastAPI). Especificação: specs/04-interface (REQ-I-17).
FROM python:3.12.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TRACES_DIR=/app/traces

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && useradd --uid 1000 --create-home app \
 && mkdir -p /app/traces && chown app /app/traces

COPY app/ app/
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
