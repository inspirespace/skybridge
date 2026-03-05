FROM python:3.12-slim

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/venv

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN apt-get update \
    && rm -rf /var/lib/apt/lists/* \
    && uv sync --frozen

COPY src ./src

ENV PATH="/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1

# Base image for local mock services (mock-cloudahoy and mock-flysto).
# The service command is provided by docker-compose.
