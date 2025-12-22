FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
  && python -m playwright install --with-deps chromium

COPY src/ /app/src/

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "src.cli"]
