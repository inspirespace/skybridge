FROM mcr.microsoft.com/playwright/python:v1.57.0-noble AS base

RUN pip install --no-cache-dir uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

FROM base AS prod
WORKDIR /app
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev
COPY src/ /app/src/

ENTRYPOINT ["python", "-m", "src.core.cli"]
