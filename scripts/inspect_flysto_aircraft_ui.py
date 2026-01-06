"""scripts/inspect_flysto_aircraft_ui.py module."""
import os
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_PATH = Path('data/discovery/flysto_aircraft_ui.json')
SCREENSHOT = Path('data/discovery/flysto_aircraft_ui.png')


def main() -> None:
    email = os.getenv('FLYSTO_EMAIL')
    password = os.getenv('FLYSTO_PASSWORD')
    if not email or not password:
        raise SystemExit('Missing FLYSTO_EMAIL or FLYSTO_PASSWORD')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto('https://www.flysto.net/login', wait_until='load')
        page.locator("input[type='email']").first.fill(email)
        page.locator("input[type='password']").first.fill(password)
        page.keyboard.press('Enter')
        page.wait_for_load_state('networkidle')

        page.goto('https://www.flysto.net/aircraft', wait_until='load')
        page.wait_for_timeout(5000)

        buttons = [b for b in page.locator('button').all_inner_texts() if b.strip()]
        links = [l for l in page.locator('a').all_inner_texts() if l.strip()]
        inputs = page.locator('input').all()
        placeholders = [inp.get_attribute('placeholder') for inp in inputs if inp.get_attribute('placeholder')]

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps({
            'buttons': buttons,
            'links': links,
            'placeholders': placeholders,
        }, indent=2))
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        browser.close()


if __name__ == '__main__':
    main()
