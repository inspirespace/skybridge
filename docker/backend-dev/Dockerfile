FROM python:3.12-slim

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/venv

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && uv sync --frozen

COPY src ./src
COPY scripts ./scripts

ENV PATH="/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "uvicorn", "src.backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
