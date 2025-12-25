FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

RUN apt-get update \
  && apt-get install -y --no-install-recommends docker.io git \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /workspaces/skybridge

COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
  pip install --no-cache-dir -r /tmp/requirements.txt

ENV PYTHONUNBUFFERED=1
