# syntax=docker/dockerfile:1
# Set Python version, download image
FROM alexanderklemps/astra-web:astra-09-24

COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install locked runtime dependencies before copying application code.
COPY pyproject.toml uv.lock /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Copy over rest of directory
COPY . /app
RUN chmod 777 start.sh

# Set api key env variable
ARG API_KEY
ENV API_KEY=${API_KEY}
ARG BINARY_PATH
ENV ASTRA_BINARY_PATH=${BINARY_PATH}

# Run FastAPI server
ENTRYPOINT ["/bin/bash", "-c", "./start.sh"]
