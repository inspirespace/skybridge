"""scripts/probe_cloudahoy_debrief.py module."""
import os
import re
import time

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
    response = session.post(
        "https://www.cloudahoy.com/api/signin.cgi?form",
        data={"email": email, "password": password},
        timeout=60,
    )
    sid3 = extract_cookie_value(response.text, "SID3")
    user3 = extract_cookie_value(response.text, "USER3")
    email3 = extract_cookie_value(response.text, "EMAIL3")
    if not sid3 or not user3 or not email3:
        raise SystemExit("Failed to extract CloudAhoy session cookies from login response")

    for k, v in ("SID3", sid3), ("USER3", user3), ("EMAIL3", email3):
        session.cookies.set(k, v, domain="www.cloudahoy.com", path="/")

    bi = f"CLI{int(time.time())}"

    flights_payload = {
        "userName": False,
        "initialCall": True,
        "EMAIL3": email3,
        "SID3": sid3,
        "STLI": None,
        "USER3": user3,
        "BI": bi,
        "PH": {"n": [], "t": []},
        "wlh": "https://www.cloudahoy.com/flights/",
    }
    flights = session.post(
        "https://www.cloudahoy.com/api/t-flights.cgi",
        json=flights_payload,
        timeout=60,
    ).json().get("flights", [])

    if not flights:
        raise SystemExit("No flights returned")

    flight = flights[0]
    key = flight.get("key")
    debrief_payload = {
        "flight": key,
        "EMAIL3": email3,
        "SID3": sid3,
        "STLI": None,
        "USER3": user3,
        "BI": bi,
        "PH": {"n": [], "t": []},
        "wlh": "https://www.cloudahoy.com/debrief/",
    }

    resp = session.post(
        "https://www.cloudahoy.com/api/t-debrief.cgi",
        json=debrief_payload,
        timeout=60,
    )
    print(resp.status_code, resp.text[:200])


if __name__ == "__main__":
    main()
