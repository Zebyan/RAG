FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd -g 1000 appuser \
    && useradd -u 1000 -g appuser -m appuser

COPY --from=builder /wheels /wheels

RUN pip install --no-cache-dir /wheels/* \
    && pip cache purge \
    && rm -rf /wheels

COPY app ./app
COPY openapi.yaml ./openapi.yaml

RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/v1/health').read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]