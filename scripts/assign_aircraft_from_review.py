import json
import os
from pathlib import Path

from src.flysto.client import FlyStoClient, _decode_flysto_payload

import requests


def main() -> None:
    exports_dir = Path(os.getenv("EXPORTS_DIR", "data/cloudahoy_exports"))
    if not exports_dir.exists():
        raise SystemExit(f"Missing exports dir: {exports_dir}")

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

    meta_map = {}
    for meta_path in exports_dir.glob("*.meta.json"):
        try:
            data = json.loads(meta_path.read_text())
        except json.JSONDecodeError:
            continue
        tail = data.get("tail_number") or data.get("tailNumber")
        if not isinstance(tail, str) or not tail.strip():
            continue
        filename = meta_path.name.replace(".meta.json", ".gpx")
        meta_map[filename] = {"tail_number": tail.strip(), "aircraft_type": data.get("aircraft_type")}

    session = requests.Session()
    client._ensure_session(session)
    params = {"type": "flight", "logs": 250, "order": "descending"}
    resp = session.get(client.base_url.rstrip("/") + "/api/log-list", params=params, timeout=60)
    log_ids = _decode_flysto_payload(resp.text)
    if isinstance(log_ids, str):
        try:
            log_ids = json.loads(log_ids)
        except json.JSONDecodeError:
            log_ids = []
    log_ids = [str(x) for x in (log_ids or [])]
    if not log_ids:
        raise SystemExit("No FlySto logs found to assign.")

    keys = "57,tf,ec,hq,86,b2,lb,8q,p2,85,bl,hk,4n,ee,yu,1y,t3,ng,ho,hq,x9,g3,6n,hq,0s,83,6h,am"
    summary = session.get(
        client.base_url.rstrip("/") + "/api/log-summary",
        params={"logs": ",".join(log_ids), "keys": keys, "update": "true"},
        timeout=60,
    )
    decoded = _decode_flysto_payload(summary.text)
    if isinstance(decoded, str):
        try:
            decoded = json.loads(decoded)
        except json.JSONDecodeError:
            decoded = {}
    items = decoded.get("items", []) if isinstance(decoded, dict) else []
    candidates = []
    for item in items:
        summary_data = item.get("summary", {}).get("data", {})
        signature = summary_data.get("6h")
        files = summary_data.get("t3") or []
        for entry in files:
            filename = entry.get("file")
            log_format = entry.get("format") or "GenericGpx"
            if filename:
                candidates.append((filename, signature, log_format))

    if not candidates:
        raise SystemExit("No log files found in FlySto summary.")

    for filename, signature, log_format in candidates:
        meta = meta_map.get(filename)
        if not meta:
            print("SKIP no metadata", filename)
            continue
        tail_number = meta.get("tail_number")
        aircraft_type = meta.get("aircraft_type")
        aircraft = client.ensure_aircraft(tail_number, aircraft_type)
        if not aircraft or not aircraft.get("id"):
            print("SKIP no aircraft", filename)
            continue
        if not signature:
            print("SKIP no signature", filename)
            continue
        client.assign_aircraft(str(aircraft.get("id")), log_format_id=log_format, system_id=signature)
        print("OK", filename, "->", tail_number)


if __name__ == "__main__":
    main()
