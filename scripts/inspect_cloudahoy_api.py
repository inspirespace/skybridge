import json
import os
from pathlib import Path

import requests


def redact(value: str) -> str:
    return "REDACTED" if value else value


def main() -> None:
    email = os.getenv("CLOUD_AHOY_EMAIL")
    password = os.getenv("CLOUD_AHOY_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing CLOUD_AHOY_EMAIL or CLOUD_AHOY_PASSWORD")

    output_dir = Path("data/discovery")
    output_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    login_url = "https://www.cloudahoy.com/api/signin.cgi?form"
    response = session.post(
        login_url,
        data={"email": email, "password": password},
        timeout=60,
    )

    payload = {
        "login_status": response.status_code,
        "login_headers": dict(response.headers),
        "login_text": response.text[:1000],
        "cookies": [cookie.name for cookie in session.cookies],
    }

    (output_dir / "cloudahoy_login.json").write_text(
        json.dumps(payload, indent=2)
    )

    # Attempt t-flights.cgi using cookies + a minimal payload.
    flights_url = "https://www.cloudahoy.com/api/t-flights.cgi"
    test_payload = {"initialCall": True}
    flights_response = session.post(flights_url, json=test_payload, timeout=60)

    flights_payload = {
        "status": flights_response.status_code,
        "headers": dict(flights_response.headers),
        "text": flights_response.text[:1000],
    }

    (output_dir / "cloudahoy_t_flights_probe.json").write_text(
        json.dumps(flights_payload, indent=2)
    )

    print("Wrote discovery files to data/discovery")


if __name__ == "__main__":
    main()
