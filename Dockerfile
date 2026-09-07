# STAGE 1: Builder — install deps, download ML models
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt          # Layer cached
RUN python -m spacy download en_core_web_sm                 # Pre-download
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('BAAI/bge-small-en-v1.5')"

# STAGE 2: Production — no build tools, smaller, secure
FROM python:3.11-slim AS production
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# SECURITY: non-root user
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup appuser

WORKDIR /app
# Copy model cache and chown it so appuser can read it
COPY --from=builder --chown=appuser:appgroup /root/.cache /app/.cache
ENV HF_HOME=/app/.cache

COPY --chown=appuser:appgroup . .
USER appuser    # ← runs as non-root

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

ENV APP_ENV=production PYTHONUNBUFFERED=1
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000","--workers","2"]
