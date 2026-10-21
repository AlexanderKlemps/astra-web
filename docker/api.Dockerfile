# syntax=docker/dockerfile:1
ARG BASE_IMAGE=alexanderklemps/astra-web:astra-py314-2026-10-09
FROM ghcr.io/astral-sh/uv:0.12.21 AS uv
FROM ${BASE_IMAGE} AS api

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install locked runtime dependencies before copying application code.
COPY pyproject.toml uv.lock /app/
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Copy application code only; data, credentials, and development tools stay out.
COPY astra_web /app/astra_web
COPY --chmod=755 start.sh /app/start.sh
RUN mkdir -p /app/data/generator /app/data/simulation

# Run FastAPI server
ENTRYPOINT ["/app/start.sh"]
