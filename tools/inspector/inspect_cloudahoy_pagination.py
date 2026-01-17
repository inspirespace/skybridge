"""tools/inspector/inspect_cloudahoy_pagination.py module."""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def scrub(payload: dict) -> dict:
    redacted = dict(payload)
    for key in ("EMAIL3", "SID3", "USER3"):
        if key in redacted:
            redacted[key] = "***redacted***"
    return redacted


def main() -> None:
    email = os.getenv("CLOUD_AHOY_EMAIL")
    password = os.getenv("CLOUD_AHOY_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing CLOUD_AHOY_EMAIL or CLOUD_AHOY_PASSWORD")

    output_dir = Path("data/discovery")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "cloudahoy_t_flights_requests.json"

    captured: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        def on_request(request) -> None:
            if "t-flights.cgi" not in request.url:
                return
            post_data = request.post_data
            data = post_data() if callable(post_data) else post_data
            payload = None
            if data:
                try:
                    payload = json.loads(data)
                except Exception:
                    payload = {"raw": data}
            captured.append({"url": request.url, "payload": scrub(payload or {})})

        def on_response(response) -> None:
            if "t-flights.cgi" not in response.url:
                return
            request_payload = {}
            try:
                post_data = response.request.post_data
                data = post_data() if callable(post_data) else post_data
                if data:
                    request_payload = scrub(json.loads(data))
            except Exception:
                request_payload = {}
            payload = None
            try:
                payload = response.json()
            except Exception:
                try:
                    payload = json.loads(response.text())
                except Exception:
                    payload = {"raw": response.text()[:2000]}
            captured.append(
                {
                    "url": response.url,
                    "status": response.status,
                    "headers": dict(response.headers),
                    "response": payload,
                    "request": request_payload,
                }
            )

        page.on("request", on_request)
        page.on("response", on_response)

        page.goto("https://www.cloudahoy.com/login.php", wait_until="load")
        page.fill("input[name=email]", email)
        page.fill("input[name=password]", password)
        page.click("#btnlogin")
        page.wait_for_load_state("load")

        page.goto("https://www.cloudahoy.com/flights/", wait_until="load")
        page.wait_for_timeout(1500)

        load_more = page.locator("button:has-text('Load more'), a:has-text('Load more')")
        if load_more.count() > 0 and not load_more.first.is_disabled():
            def _post_data(request) -> str:
                post_data = request.post_data
                return post_data() if callable(post_data) else (post_data or "")

            with page.expect_response(
                lambda r: "t-flights.cgi" in r.url
                and "last" in _post_data(r.request)
            ):
                load_more.first.click()
            page.wait_for_load_state("load")
            page.wait_for_timeout(1500)

        browser.close()

    output_path.write_text(json.dumps(captured, indent=2))
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
