import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    email = os.getenv("FLYSTO_EMAIL")
    password = os.getenv("FLYSTO_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing FLYSTO_EMAIL or FLYSTO_PASSWORD")

    file_path = os.getenv("DIAG_UPLOAD_FILE")
    if not file_path:
        raise SystemExit("Missing DIAG_UPLOAD_FILE")
    file_path = str(Path(file_path).resolve())

    output_dir = Path("data/discovery")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "flysto_upload_requests.json"

    captured: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        def log_request(request) -> None:
            url = request.url
            if "flysto.net/api" not in url:
                return
            if "log" not in url and "upload" not in url:
                return
            headers = dict(request.headers)
            for key in list(headers.keys()):
                if key.lower() in {"authorization", "cookie"}:
                    headers[key] = "***redacted***"
            post_data = request.post_data
            data = post_data() if callable(post_data) else post_data
            captured.append(
                {
                    "url": url,
                    "method": request.method,
                    "headers": headers,
                    "post_data": data[:2000] if isinstance(data, str) else None,
                }
            )

        page.on("request", log_request)

        for attempt in range(3):
            page.goto("https://www.flysto.net/login", wait_until="load")
            page.wait_for_timeout(3000)
            if page.get_by_text("Server error").count() > 0:
                page.screenshot(path=output_dir / f"flysto_login_server_error_{attempt}.png", full_page=True)
                if page.get_by_text("Try again").count() > 0:
                    page.get_by_text("Try again").first.click()
                    page.wait_for_timeout(2000)
                continue
            try:
                page.wait_for_selector("input[type='email']", timeout=15000, state="attached")
                page.wait_for_selector("input[type='password']", timeout=15000, state="attached")
                break
            except Exception:
                page.screenshot(path=output_dir / f"flysto_login_wait_timeout_{attempt}.png", full_page=True)
                if attempt == 2:
                    raise
        page.locator("input[type='email']").first.fill(email)
        page.locator("input[type='password']").first.fill(password)
        page.keyboard.press("Enter")
        page.wait_for_load_state("load")
        page.wait_for_timeout(3000)

        page.goto("https://www.flysto.net/logs", wait_until="load")
        page.wait_for_timeout(2000)

        if page.get_by_text("Load logs").count() > 0:
            page.get_by_text("Load logs").first.click()
            page.wait_for_timeout(1000)
        if page.get_by_text("Browse files").count() > 0:
            page.get_by_text("Browse files").first.click()
            page.wait_for_timeout(1000)

        file_inputs = page.locator("input[type=file]")
        if file_inputs.count() == 0:
            page.screenshot(path=output_dir / "flysto_upload_missing_input.png", full_page=True)
            raise RuntimeError("Upload file input not found")
        file_inputs.first.set_input_files(file_path)
        page.wait_for_timeout(2000)

        if page.get_by_text("Upload").count() > 0:
            page.get_by_text("Upload").first.click()
        elif page.get_by_text("Import").count() > 0:
            page.get_by_text("Import").first.click()

        page.wait_for_timeout(5000)
        browser.close()

    out_path.write_text(json.dumps(captured, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
