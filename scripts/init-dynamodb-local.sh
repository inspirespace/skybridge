#!/bin/sh
set -euo pipefail

endpoint="${DYNAMODB_ENDPOINT_URL:-http://dynamodb:8000}"
jobs_table="${DYNAMO_JOBS_TABLE:-skybridge-jobs}"
creds_table="${DYNAMO_CREDENTIALS_TABLE:-skybridge-credentials}"

until aws dynamodb list-tables --endpoint-url "$endpoint" >/dev/null 2>&1; do
  sleep 1
done

if ! aws dynamodb describe-table --endpoint-url "$endpoint" --table-name "$jobs_table" >/dev/null 2>&1; then
  aws dynamodb create-table \
    --endpoint-url "$endpoint" \
    --table-name "$jobs_table" \
    --attribute-definitions AttributeName=user_id,AttributeType=S AttributeName=job_id,AttributeType=S \
    --key-schema AttributeName=user_id,KeyType=HASH AttributeName=job_id,KeyType=RANGE \
    --global-secondary-indexes '[
      {
        "IndexName": "job_id-index",
        "KeySchema": [{"AttributeName": "job_id", "KeyType": "HASH"}],
        "Projection": {"ProjectionType": "ALL"},
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
      }
    ]' \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
fi

if ! aws dynamodb describe-table --endpoint-url "$endpoint" --table-name "$creds_table" >/dev/null 2>&1; then
  aws dynamodb create-table \
    --endpoint-url "$endpoint" \
    --table-name "$creds_table" \
    --attribute-definitions AttributeName=token,AttributeType=S \
    --key-schema AttributeName=token,KeyType=HASH \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
fi
