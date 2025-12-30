from __future__ import annotations

import os
import time
from pathlib import Path

from .store import JobStore

DATA_DIR = Path(os.environ.get("BACKEND_DATA_DIR", "data/backend/jobs"))


def run() -> None:
    store = JobStore(DATA_DIR)
    while True:
        jobs = store.list_jobs(user_id=os.environ.get("BACKEND_USER_ID", "demo-user"))
        print(f"[worker] observed {len(jobs)} jobs")
        time.sleep(10)


if __name__ == "__main__":
    run()
