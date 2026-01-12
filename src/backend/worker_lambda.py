"""Local runner that processes SQS messages using the Lambda worker handler."""
from __future__ import annotations

import json
import os
import time

from .lambda_handlers import sqs_worker_handler

_sqs_client = None


def _sqs_region() -> str:
    """Internal helper for sqs region."""
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"

def _sqs_endpoint_url() -> str | None:
    """Internal helper for sqs endpoint url."""
    value = os.getenv("SQS_ENDPOINT_URL")
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _queue_url() -> str:
    """Internal helper for queue url."""
    return os.getenv("SQS_QUEUE_URL") or ""


def _use_queue() -> bool:
    """Internal helper for use queue."""
    return (os.getenv("BACKEND_SQS_ENABLED") or "false").lower() in {"1", "true", "yes", "on"}


def _get_sqs_client():
    """Internal helper for get sqs client."""
    global _sqs_client
    if _sqs_client is None:
        import boto3

        _sqs_client = boto3.client(
            "sqs",
            region_name=_sqs_region(),
            endpoint_url=_sqs_endpoint_url(),
        )
    return _sqs_client


def run() -> None:
    """Poll SQS and invoke the Lambda handler locally."""
    if not _use_queue():
        raise RuntimeError("BACKEND_SQS_ENABLED=1 is required for lambda-style worker")
    queue_url = _queue_url()
    if not queue_url:
        raise RuntimeError("SQS_QUEUE_URL not configured")
    while True:
        response = _get_sqs_client().receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=10,
            VisibilityTimeout=900,
        )
        messages = response.get("Messages") or []
        if not messages:
            continue
        event = {
            "Records": [{"body": msg.get("Body")} for msg in messages if msg.get("Body")]
        }
        sqs_worker_handler(event, None)
        for message in messages:
            receipt = message.get("ReceiptHandle")
            if receipt:
                _get_sqs_client().delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
        time.sleep(0.1)


if __name__ == "__main__":
    run()
