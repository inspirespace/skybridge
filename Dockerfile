FROM mcr.microsoft.com/playwright/python:v1.57.0-noble AS base

RUN pip install --no-cache-dir uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

FROM base AS devcontainer
RUN apt-get update \
  && apt-get install -y --no-install-recommends imagemagick \
  && rm -rf /var/lib/apt/lists/*
# Pre-create the project venv so VS Code can resolve python.defaultInterpreterPath
# before post-start commands run uv sync.
RUN uv venv /opt/venv --python /usr/bin/python3 \
  && /opt/venv/bin/python --version
RUN command -v convert >/dev/null

FROM base AS prod
WORKDIR /app
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev
COPY src/ /app/src/

ENTRYPOINT ["python", "-m", "src.core.cli"]
