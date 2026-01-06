"""scripts/probe_cloudahoy_flights.py module."""
import json
import os
import re
from pathlib import Path

import requests


def extract_cookie_value(html: str, name: str) -> str | None:
    match = re.search(rf"setCookie\(\"{name}\",\"([^\"]+)\"", html)
    return match.group(1) if match else None


def main() -> None:
    email = os.getenv("CLOUD_AHOY_EMAIL")
    password = os.getenv("CLOUD_AHOY_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing CLOUD_AHOY_EMAIL or CLOUD_AHOY_PASSWORD")

    session = requests.Session()
    login_url = "https://www.cloudahoy.com/api/signin.cgi?form"
    response = session.post(
        login_url,
        data={"email": email, "password": password},
        timeout=60,
    )

    sid3 = extract_cookie_value(response.text, "SID3")
    user3 = extract_cookie_value(response.text, "USER3")
    email3 = extract_cookie_value(response.text, "EMAIL3")

    if not sid3 or not user3 or not email3:
        raise SystemExit("Failed to extract CloudAhoy session cookies from login response")

    session.cookies.set("SID3", sid3, domain="www.cloudahoy.com", path="/")
    session.cookies.set("USER3", user3, domain="www.cloudahoy.com", path="/")
    session.cookies.set("EMAIL3", email3, domain="www.cloudahoy.com", path="/")

    flights_url = "https://www.cloudahoy.com/api/t-flights.cgi"
    payload = {
        "userName": False,
        "initialCall": True,
        "EMAIL3": email3,
        "SID3": sid3,
        "USER3": user3,
        "PH": {"n": [], "t": []},
        "wlh": "https://www.cloudahoy.com/flights/",
    }

    flights_resp = session.post(flights_url, json=payload, timeout=60)
    flights_text = flights_resp.text

    output_dir = Path("data/discovery")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "cloudahoy_t_flights_response.json").write_text(flights_text)

    print("status", flights_resp.status_code)
    print(flights_text[:500])


if __name__ == "__main__":
    main()
