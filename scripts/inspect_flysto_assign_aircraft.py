import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


OUTPUT_PATH = Path("data/discovery/flysto_assign_requests.json")
SCREENSHOT_PATH = Path("data/discovery/flysto_assign_screen.png")


def main() -> None:
    email = os.getenv("FLYSTO_EMAIL")
    password = os.getenv("FLYSTO_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing FLYSTO_EMAIL or FLYSTO_PASSWORD")

    captured = []

    def handle_request(request) -> None:
        if request.resource_type not in {"xhr", "fetch"}:
            return
        safe_headers = dict(request.headers)
        safe_headers.pop("cookie", None)
        safe_headers.pop("authorization", None)
        post_data = request.post_data
        if "/api/login" in request.url:
            post_data = "<redacted>"
        payload = {
            "url": request.url,
            "method": request.method,
            "headers": safe_headers,
            "post_data": post_data,
        }
        captured.append({"request": payload})

    def handle_response(response) -> None:
        if "/api/" not in response.url:
            return
        captured.append(
            {
                "response": {
                    "url": response.url,
                    "status": response.status,
                }
            }
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.on("request", handle_request)
        page.on("response", handle_response)

        page.goto("https://www.flysto.net/login", wait_until="load")
        page.locator("input[type='email']").first.fill(email)
        page.locator("input[type='password']").first.fill(password)
        login_button = page.get_by_role("button", name="Login")
        if login_button.count() > 0:
            login_button.first.click()
        else:
            page.keyboard.press("Enter")
        page.wait_for_timeout(3000)

        page.goto("https://www.flysto.net/logs", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        cookie_accept = page.get_by_role("button", name="Accept")
        if cookie_accept.count() > 0:
            cookie_accept.first.click()
            page.wait_for_timeout(500)

        # Try to switch aircraft filter to "Unknown aircraft" if available.
        page.evaluate(
            """
            (label) => {
              const el = Array.from(document.querySelectorAll('*'))
                .find(node => node.textContent && node.textContent.trim().startsWith(label));
              if (!el) return;
              const button = el.closest('button,[role="button"]');
              if (button) button.click();
            }
            """,
            "All aircraft",
        )
        page.wait_for_timeout(500)
        page.evaluate(
            """
            (label) => {
              const el = Array.from(document.querySelectorAll('*'))
                .find(node => node.textContent && node.textContent.trim().includes(label));
              if (!el) return;
              const button = el.closest('button,[role="option"],[role="menuitem"],[role="button"]');
              if (button) button.click();
            }
            """,
            "Unknown aircraft",
        )
        page.wait_for_timeout(1000)

        # If there's a dedicated "Unknown aircraft" tab, open it to force the assign flow.
        unknown_tab = page.get_by_text("Unknown aircraft", exact=True)
        if unknown_tab.count() > 0:
            unknown_tab.first.click()
            page.wait_for_timeout(1000)

        # Select first visible data row (skip separators/headers).
        unknown_rows = page.locator(
            "table tbody tr[data-row-id]:not([data-row-id='separator'])",
            has_text="Unknown aircraft",
        )
        if unknown_rows.count() > 0:
            row = unknown_rows.first
        else:
            row = page.locator(
                "table tbody tr[data-row-id]:not([data-row-id='separator'])"
            ).first
        if row.count() == 0:
            page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
            raise RuntimeError("No log rows found.")
        row_handle = row.element_handle()
        if row_handle is None:
            page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
            raise RuntimeError("Log row not attached.")
        row.scroll_into_view_if_needed()
        checkbox = row.locator("input[type='checkbox']").first
        if checkbox.count() > 0:
            handle = checkbox.element_handle()
            if handle is not None:
                page.evaluate(
                    "(el) => el.scrollIntoView({block: 'center', inline: 'center'})",
                    handle,
                )
                page.wait_for_timeout(200)
                page.evaluate("(el) => el.click()", handle)
            else:
                checkbox.first.click(force=True)
        else:
            # Fallback: click the row itself if checkbox is hidden.
            page.evaluate("(el) => el.click()", row_handle)
        page.wait_for_timeout(1000)

        # Try to open assign-aircraft action from toolbar or row context.
        assign_button = page.get_by_role("button", name="Assign aircraft")
        if assign_button.count() > 0:
            assign_button.first.click()
        else:
            text_match = page.get_by_text("Assign aircraft", exact=False)
            if text_match.count() > 0:
                text_match.first.click()
            else:
                # Try toolbar icon buttons for aircraft assignment.
                toolbar_button = page.locator(
                    "button[aria-label*='aircraft' i], button[title*='aircraft' i]"
                )
                if toolbar_button.count() > 0:
                    toolbar_button.first.click()
                    page.wait_for_timeout(500)
                page.evaluate(
                    """(el) => el.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true}))""",
                    row_handle,
                )
                page.wait_for_timeout(500)
                text_match = page.get_by_text("Assign aircraft", exact=False)
                if text_match.count() > 0:
                    text_match.first.click()
                else:
                    actions = page.locator(
                        "button[aria-label*='Action' i], button[aria-label*='More' i], button[aria-label*='Menu' i]"
                    )
                    if actions.count() > 0:
                        actions.first.click()
        page.wait_for_timeout(1000)

        # If no assign dialog opened, try clicking the aircraft cell to change it.
        option = page.get_by_role("option").first
        if option.count() == 0:
            cells = row.locator("td")
            if cells.count() > 1:
                aircraft_cell = cells.nth(1)
                page.evaluate("(el) => el.click()", aircraft_cell.element_handle())
                page.wait_for_timeout(500)
                option = page.get_by_role("option").first

        # Fallback: open details drawer and try to edit aircraft there.
        if option.count() == 0:
            row.dblclick()
            page.wait_for_timeout(1000)
            dialog = page.locator("[role='dialog'], .modal, .drawer, .panel")
            combo = dialog.locator("[role='combobox'], select").first
            if combo.count() > 0:
                combo.first.click()
                page.wait_for_timeout(500)
                option = page.get_by_role("option").first

        # Try to select the first aircraft option and confirm.
        option = page.get_by_role("option").first
        if option.count() > 0:
            option.first.click()
        page.wait_for_timeout(500)

        confirm = page.get_by_role("button", name="Assign")
        if confirm.count() > 0:
            confirm.first.click()
        else:
            confirm = page.get_by_role("button", name="Save")
            if confirm.count() > 0:
                confirm.first.click()
        page.wait_for_timeout(4000)

        SCREENSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(captured, indent=2))
        browser.close()


if __name__ == "__main__":
    main()
