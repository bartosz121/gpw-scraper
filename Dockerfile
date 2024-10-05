FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

RUN --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

ADD . /app

RUN uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"

CMD [ "uvicorn", "--workers", "1", "--factory", "gpw_scraper.api:create_app", "--host", "0.0.0.0", "--port", "8080" ]