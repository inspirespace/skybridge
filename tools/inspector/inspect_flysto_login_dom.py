"""tools/inspector/inspect_flysto_login_dom.py module."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    output_dir = Path("data/discovery")
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.flysto.net/login", wait_until="load")
        page.wait_for_timeout(8000)

        inputs = page.evaluate(
            """
            () => {
                const items = [];
                document.querySelectorAll('input').forEach((el) => {
                    items.push({
                        type: el.getAttribute('type'),
                        name: el.getAttribute('name'),
                        id: el.getAttribute('id'),
                        placeholder: el.getAttribute('placeholder'),
                    });
                });
                const iframes = [];
                document.querySelectorAll('iframe').forEach((el) => {
                    iframes.push({
                        src: el.getAttribute('src'),
                        id: el.getAttribute('id'),
                        name: el.getAttribute('name'),
                    });
                });
                return { url: window.location.href, inputs: items, iframes, html: document.body.innerHTML.slice(0, 2000) };
            }
            """
        )
        (output_dir / "flysto_login_inputs.json").write_text(
            json.dumps(inputs, indent=2)
        )
        frame_report = []
        for frame in page.frames:
            try:
                frame_inputs = frame.evaluate(
                    """
                    () => {
                        const items = [];
                        document.querySelectorAll('input').forEach((el) => {
                            items.push({
                                type: el.getAttribute('type'),
                                name: el.getAttribute('name'),
                                id: el.getAttribute('id'),
                                placeholder: el.getAttribute('placeholder'),
                            });
                        });
                        return items;
                    }
                    """
                )
            except Exception:
                frame_inputs = []
            frame_report.append({"url": frame.url, "inputs": frame_inputs})
        (output_dir / "flysto_login_frames.json").write_text(
            json.dumps(frame_report, indent=2)
        )
        page.screenshot(path=output_dir / "flysto_login.png", full_page=True)
        page.wait_for_timeout(5000)
        page.screenshot(path=output_dir / "flysto_login_late.png", full_page=True)
        browser.close()

    print("Wrote data/discovery/flysto_login_inputs.json")


if __name__ == "__main__":
    main()
