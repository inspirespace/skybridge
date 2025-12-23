import json
import os
from pathlib import Path

from src.flysto.client import FlyStoClient
from src.migration import _extract_metadata


def main() -> None:
    review_path = Path(os.getenv("REVIEW_PATH", "data/review.json"))
    if not review_path.exists():
        raise SystemExit(f"Missing review manifest: {review_path}")

    data = json.loads(review_path.read_text())
    items = data.get("items", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise SystemExit("Invalid review manifest format.")

    client = FlyStoClient(
        api_key="",
        base_url=os.getenv("FLYSTO_BASE_URL", "https://www.flysto.net"),
        upload_url=os.getenv("FLYSTO_LOG_UPLOAD_URL"),
        session_cookie=os.getenv("FLYSTO_SESSION_COOKIE"),
        api_version=os.getenv("FLYSTO_API_VERSION"),
        email=os.getenv("FLYSTO_EMAIL"),
        password=os.getenv("FLYSTO_PASSWORD"),
    )
    if not client.prepare():
        raise SystemExit("FlySto API not available. Verify credentials or session cookie.")

    for item in items:
        file_path = item.get("file_path") or item.get("filePath")
        raw_payload = item.get("raw_payload") or {}
        if not file_path:
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = _extract_metadata(raw_payload) if isinstance(raw_payload, dict) else {}
        tail_number = metadata.get("tail_number")
        aircraft_type = metadata.get("aircraft_type")
        if not tail_number:
            print("SKIP no tail", item.get("flight_id"))
            continue
        aircraft = client.ensure_aircraft(tail_number, aircraft_type)
        if not aircraft or not aircraft.get("id"):
            print("SKIP no aircraft", item.get("flight_id"))
            continue
        filename = Path(file_path).name
        log_id, signature, log_format = client.resolve_log_for_file(filename)
        if not signature:
            print("SKIP no signature", filename)
            continue
        client.assign_aircraft(str(aircraft.get("id")), log_format_id=log_format or "GenericGpx", system_id=signature)
        print("OK", filename, "->", tail_number)


if __name__ == "__main__":
    main()
