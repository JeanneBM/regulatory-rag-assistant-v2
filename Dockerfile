# Web app and ingest job share this image (the job overrides the command).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src \
    REGRAG_LOCAL_DIR=/tmp/regrag

WORKDIR /app

# Hash-pinned runtime dependencies only; no build tools or test packages.
COPY requirements.lock .
RUN pip install --require-hashes --no-deps -r requirements.lock

COPY src ./src
COPY eval ./eval
RUN python -m compileall -q src \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin regrag

USER 10001
EXPOSE 8000
CMD ["python", "-m", "regrag", "serve", "--host", "0.0.0.0", "--port", "8000"]
