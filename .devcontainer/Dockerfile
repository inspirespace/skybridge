FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

RUN apt-get update \
  && apt-get install -y --no-install-recommends docker.io git \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /workspaces/skybridge

COPY pyproject.toml uv.lock /workspaces/skybridge/
RUN pip install --no-cache-dir uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --extra dev

ENV PYTHONUNBUFFERED=1
