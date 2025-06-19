ARG ENVIRONMENT=LOCAL

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ARG ENVIRONMENT

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    if [ "${ENVIRONMENT}" = "PRODUCTION" ]; then \
    uv sync --frozen --no-install-project --no-dev; \
    else \
    uv sync --frozen --no-install-project --all-groups; \
    fi

ADD . /app

RUN if [ "${ENVIRONMENT}" = "PRODUCTION" ]; then \
    uv sync --frozen --no-dev; \
    else \
    uv sync --frozen --all-groups; \
    fi


FROM python:3.13-slim-bookworm AS final

ARG ENVIRONMENT

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder --chown=app:app /app /app


RUN if [ "${ENVIRONMENT}" = "PRODUCTION" ]; then rm -rf /app/tests/cassettes; fi

WORKDIR /app

RUN mkdir /tmp/prometheus

ENV PATH="/app/.venv/bin:$PATH"

CMD [ "uvicorn", "--workers", "1", "--factory", "gpw_scraper.api:create_app", "--host", "0.0.0.0", "--port", "8080" ]