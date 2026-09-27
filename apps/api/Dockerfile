# Container image for the always-on API (Path A / the container half of the
# hybrid). Streaming (SSE) and low latency work here — unlike Lambda+API Gateway.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN pip install --no-cache-dir uv

# Dependencies first for layer caching; prod install excludes the dev group.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Application code + migrations.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# Drop privileges.
RUN useradd -r -u 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
# Shell form so ${PORT} (Render/Railway/Fly inject it) expands; defaults to 8000.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
