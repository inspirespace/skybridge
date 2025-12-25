FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

COPY pyproject.toml uv.lock /app/
RUN pip install --no-cache-dir uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv sync --frozen --no-dev

COPY src/ /app/src/

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "src.cli"]
