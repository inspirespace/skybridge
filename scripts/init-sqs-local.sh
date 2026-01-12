#!/usr/bin/env sh
set -eu

if [ -z "${SQS_ENDPOINT_URL:-}" ]; then
  echo "SQS_ENDPOINT_URL is required"
  exit 1
fi

if [ -z "${SQS_QUEUE_NAME:-}" ]; then
  echo "SQS_QUEUE_NAME is required"
  exit 1
fi

attempts=0
until aws --endpoint-url "${SQS_ENDPOINT_URL}" sqs list-queues >/dev/null 2>&1; do
  attempts=$((attempts + 1))
  if [ "$attempts" -ge 30 ]; then
    echo "LocalStack SQS not ready after ${attempts} attempts" >&2
    exit 1
  fi
  sleep 1
done

aws --endpoint-url "${SQS_ENDPOINT_URL}" sqs create-queue \
  --queue-name "${SQS_QUEUE_NAME}" >/dev/null

echo "SQS queue ready: ${SQS_QUEUE_NAME}"
