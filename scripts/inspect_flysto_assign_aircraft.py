import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


OUTPUT_PATH = Path("data/discovery/flysto_assign_requests.json")
SCREENSHOT_PATH = Path("data/discovery/flysto_assign_screen.png")
DIALOG_HTML_PATH = Path("data/discovery/flysto_aircraft_dialog.html")
DIALOG_PAGE_PATH = Path("data/discovery/flysto_page.html")
CAPTURE_SCRIPT_PATH = Path("scripts/auto_assign.js")


def main() -> None:
    email = os.getenv("FLYSTO_EMAIL")
    password = os.getenv("FLYSTO_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing FLYSTO_EMAIL or FLYSTO_PASSWORD")

    captured = []

    def handle_request(request) -> None:
        if "/api/" not in request.url:
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
        # Use role=tab to avoid clicking table cells.
        page.keyboard.press("Escape")
        unknown_tab = page.get_by_role("tab", name="Unknown aircraft")
        if unknown_tab.count() == 0:
            unknown_tab = page.locator(
                "a:has-text('Unknown aircraft'), button:has-text('Unknown aircraft')"
            )
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
        # Click the row itself (not the checkbox) to open the aircraft setup dialog.
        page.evaluate(
            """
            (el) => {
              el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
              el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
              el.click();
            }
            """,
            row_handle,
        )
        page.wait_for_timeout(500)
        row.dblclick()
        page.wait_for_timeout(500)
        # Target a non-checkbox cell directly (date/from-to tend to open the dialog).
        date_cell = row.locator("td[data-column-id='date']").first
        if date_cell.count() > 0:
            page.evaluate("(el) => el.click()", date_cell.element_handle())
            page.wait_for_timeout(500)
        from_to = row.locator("td[data-column-id='from-to']").first
        if from_to.count() > 0:
            page.evaluate("(el) => el.click()", from_to.element_handle())
            page.wait_for_timeout(500)

        # Open aircraft setup banner as a fallback.
        setup_link = page.get_by_role("link", name="here")
        if setup_link.count() > 0:
            setup_link.first.click()
            page.wait_for_timeout(1000)

        # If we're on the Aircraft page, click the "Aircraft setup" button.
        setup_button = page.get_by_role("button", name="Aircraft setup")
        if setup_button.count() > 0:
            setup_button.first.click()
            page.wait_for_timeout(1000)

        # In the aircraft setup dialog, select an existing aircraft and proceed.
        dialog = page.locator(
            "div[role='dialog'], .modal, .dialog, .flysto-dialog, .MuiDialog-root"
        )
        if dialog.count() > 0:
            dialog.first.wait_for(state="visible", timeout=5000)
            DIALOG_HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
            DIALOG_HTML_PATH.write_text(dialog.first.inner_html())
        else:
            DIALOG_PAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
            DIALOG_PAGE_PATH.write_text(page.content())

        captured.append(
            {
                "dialog_state_before": page.evaluate(
                    """
                    () => {
                      const root = document.querySelector("[role='dialog']")
                        || document.querySelector(".modal")
                        || document.querySelector(".dialog")
                        || document.body;
                      const radios = Array.from(root.querySelectorAll("input[type='radio']"));
                      const labels = radios.map(r => ({
                        text: (r.closest('label')?.textContent || '').trim(),
                        checked: r.checked,
                      }));
                      const next = Array.from(root.querySelectorAll('button'))
                        .find(b => b.textContent && b.textContent.trim() === 'Next');
                      const buttons = Array.from(root.querySelectorAll('button'))
                        .map(b => ({text: (b.textContent || '').trim(), disabled: !!b.disabled}))
                        .filter(b => b.text);
                      return {labels, nextDisabled: next ? next.disabled : null, buttons};
                    }
                    """
                )
            }
        )

        action_result = page.evaluate(
            """
            () => {
              const root = document.body;
              const labels = Array.from(root.querySelectorAll('label'));
              const target = labels.find(l => l.textContent && l.textContent.includes('D-KLVW'))
                || labels.find(l => l.textContent && l.textContent.includes('OE-9487'))
                || labels.find(l => l.textContent && l.textContent.includes('D-KIER'))
                || labels.find(l => l.textContent && l.textContent.includes('D-KBUH'));
              let picked = false;
              if (target) {
                const input = target.querySelector('input[type=radio]');
                if (input) { input.click(); picked = true; }
              }
              return {rootFound: true, picked};
            }
            """
        )
        page.wait_for_timeout(600)
        action_step2 = page.evaluate(
            """
            () => {
              const root = document.body;
              const next = Array.from(root.querySelectorAll('button'))
                .find(b => b.textContent && b.textContent.trim() === 'Next');
              let clickedNext = false;
              if (next && !next.disabled) { next.click(); clickedNext = true; }
              const finish = Array.from(root.querySelectorAll('button'))
                .find(b => ['Finish','Assign','Save'].includes(b.textContent && b.textContent.trim()));
              let clickedFinish = false;
              if (finish && !finish.disabled) { finish.click(); clickedFinish = true; }
              return {clickedNext, clickedFinish};
            }
            """
        )
        captured.append({"dialog_actions": {**action_result, **action_step2}})
        page.wait_for_timeout(2000)

        captured.append(
            {
                "dialog_state_after": page.evaluate(
                    """
                    () => {
                      const root = document.querySelector("[role='dialog']")
                        || document.querySelector(".modal")
                        || document.querySelector(".dialog")
                        || document.body;
                      const radios = Array.from(root.querySelectorAll("input[type='radio']"));
                      const labels = radios.map(r => ({
                        text: (r.closest('label')?.textContent || '').trim(),
                        checked: r.checked,
                      }));
                      const next = Array.from(root.querySelectorAll('button'))
                        .find(b => b.textContent && b.textContent.trim() === 'Next');
                      const buttons = Array.from(root.querySelectorAll('button'))
                        .map(b => ({text: (b.textContent || '').trim(), disabled: !!b.disabled}))
                        .filter(b => b.text);
                      return {labels, nextDisabled: next ? next.disabled : null, buttons};
                    }
                    """
                )
            }
        )

        SCREENSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(captured, indent=2))
        browser.close()


if __name__ == "__main__":
    main()
DIALOG_PAGE_PATH = Path("data/discovery/flysto_page.html")
