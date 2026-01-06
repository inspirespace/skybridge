"""scripts/inspect_flysto_aircraft_setup.py module."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_PATH = Path('data/discovery/flysto_aircraft_setup_request.json')
ALL_PATH = Path('data/discovery/flysto_aircraft_setup_all.json')
SCREENSHOT = Path('data/discovery/flysto_aircraft_setup.png')


def main() -> None:
    email = os.getenv('FLYSTO_EMAIL')
    password = os.getenv('FLYSTO_PASSWORD')
    if not email or not password:
        raise SystemExit('Missing FLYSTO_EMAIL or FLYSTO_PASSWORD')

    captured = None
    all_requests = []

    def handle_request(request) -> None:
        nonlocal captured
        payload = {
            'url': request.url,
            'method': request.method,
            'headers': dict(request.headers),
            'post_data': request.post_data,
            'resource_type': request.resource_type,
        }
        all_requests.append(payload)
        if '/api/create-aircraft' in request.url or '/api/assign-aircraft' in request.url:
            captured = payload

    headless = os.getenv('PLAYWRIGHT_HEADLESS', '1') not in {'0', 'false', 'False'}
    slow_mo = int(os.getenv('PLAYWRIGHT_SLOWMO_MS', '0') or '0')
    channel = os.getenv('PLAYWRIGHT_CHANNEL')
    extra_args = os.getenv('PLAYWRIGHT_ARGS', '')
    args = [arg for arg in (a.strip() for a in extra_args.split(',')) if arg]
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
            channel=channel,
            args=args or None,
        )
        context = browser.new_context()
        page = context.new_page()

        page.on('console', lambda msg: all_requests.append({'console': msg.text}))
        page.on('request', handle_request)

        def handle_websocket(ws) -> None:
            try:
                ws.on('framereceived', lambda frame: all_requests.append({'websocket': {'url': ws.url, 'direction': 'received', 'payload': frame}}))
                ws.on('framesent', lambda frame: all_requests.append({'websocket': {'url': ws.url, 'direction': 'sent', 'payload': frame}}))
            except Exception:
                return

        page.on('websocket', handle_websocket)
        def handle_response(response) -> None:
            if '/api/' not in response.url:
                return
            try:
                if any(key in response.url for key in ['aircraft', 'profiles', 'model']):
                    payload = {
                        'url': response.url,
                        'status': response.status,
                        'body': response.text(),
                    }
                    all_requests.append({'response': payload})
            except Exception:
                return

        page.on('response', handle_response)

        page.goto('https://www.flysto.net/login', wait_until='load')
        page.locator("input[type='email']").first.fill(email)
        page.locator("input[type='password']").first.fill(password)
        login_button = page.get_by_role('button', name='Login')
        if login_button.count() > 0:
            login_button.first.click()
        else:
            page.keyboard.press('Enter')
        page.wait_for_timeout(2000)

        page.goto('https://www.flysto.net/logs', wait_until='load', timeout=60000)

        # if advanced setup step appears, choose create profile and continue
        if page.get_by_text('How would you like to configure your aircraft model?').count() > 0:
            option = page.get_by_text('Create profile from scratch')
            if option.count() > 0:
                option.first.click()
            next_button = page.locator('[data-gtm-id="create_aircraft_next"]')
            if next_button.count() > 0:
                next_button.first.click(force=True)
            else:
                for label in ['Next', 'Save', 'Create']:
                    button = page.get_by_role('button', name=label)
                    if button.count() > 0:
                        if button.first.is_enabled():
                            button.first.click(force=True)
                        break
            page.wait_for_timeout(3000)

        # capture any request after profile step
        page.wait_for_timeout(2000)

        # helper to fill profile step if present
        def fill_profile_step() -> None:
            if page.get_by_text('Model name').count() > 0:
                model_name = page.locator('#_r_a_')
                if model_name.count() > 0:
                    model_name.first.fill('Other')
                vso = page.locator('#_r_c_')
                if vso.count() > 0:
                    vso.first.fill('40')
                engine_count = page.locator('#_r_j_')
                if engine_count.count() > 0:
                    engine_count.first.fill('1')
                cyl_count = page.locator('#_r_l_')
                if cyl_count.count() > 0:
                    cyl_count.first.fill('4')
                engine = page.get_by_role('combobox')
                if engine.count() > 0:
                    page.evaluate("""() => {
                        const el = document.querySelector('#react-select-3-input');
                        if (el) el.focus();
                    }""")
                    page.wait_for_timeout(300)
                    page.keyboard.press('ArrowDown')
                    page.keyboard.press('Enter')
                fuel = page.locator('#_r_g_')
                if fuel.count() > 0:
                    page.evaluate("""() => {
                        const el = document.querySelector('#_r_g_');
                        if (el) el.click();
                    }""")
                else:
                    if page.get_by_text('Avgas').count() > 0:
                        page.get_by_text('Avgas').first.click()
                page.wait_for_timeout(500)
        # attempt to advance through any subsequent steps
        for step in range(3):
            next_button = page.locator('[data-gtm-id="create_aircraft_next"]')
            if next_button.count() > 0:
                fill_profile_step()
                page.evaluate("() => { const el = document.querySelector('[data-gtm-id=\"create_aircraft_next\"]'); if (el) el.click(); }")
                page.wait_for_timeout(5000)
                step_png = OUTPUT_PATH.parent / f'flysto_aircraft_setup_step{step+1}.png'
                step_html = OUTPUT_PATH.parent / f'flysto_aircraft_setup_step{step+1}.html'
                page.screenshot(path=str(step_png), full_page=True)
                step_html.write_text(page.content())
            else:
                break
        page.wait_for_timeout(5000)

        # accept cookies if present
        if page.get_by_text('Accept').count() > 0:
            page.get_by_text('Accept').first.click()
            page.wait_for_timeout(1000)

        # go to Aircraft page and open setup modal
        page.goto('https://www.flysto.net/aircraft', wait_until='load', timeout=60000)

        # if advanced setup step appears, choose create profile and continue
        if page.get_by_text('How would you like to configure your aircraft model?').count() > 0:
            option = page.get_by_text('Create profile from scratch')
            if option.count() > 0:
                option.first.click()
            next_button = page.locator('[data-gtm-id="create_aircraft_next"]')
            if next_button.count() > 0:
                next_button.first.click(force=True)
            else:
                for label in ['Next', 'Save', 'Create']:
                    button = page.get_by_role('button', name=label)
                    if button.count() > 0:
                        if button.first.is_enabled():
                            button.first.click(force=True)
                        break
            page.wait_for_timeout(3000)

        # capture any request after profile step
        page.wait_for_timeout(2000)

        # helper to fill profile step if present
        def fill_profile_step() -> None:
            if page.get_by_text('Model name').count() > 0:
                model_name = page.locator('#_r_a_')
                if model_name.count() > 0:
                    model_name.first.fill('Other')
                vso = page.locator('#_r_c_')
                if vso.count() > 0:
                    vso.first.fill('40')
                engine_count = page.locator('#_r_j_')
                if engine_count.count() > 0:
                    engine_count.first.fill('1')
                cyl_count = page.locator('#_r_l_')
                if cyl_count.count() > 0:
                    cyl_count.first.fill('4')
                engine = page.get_by_role('combobox')
                if engine.count() > 0:
                    page.evaluate("""() => {
                        const el = document.querySelector('#react-select-3-input');
                        if (el) el.focus();
                    }""")
                    page.wait_for_timeout(300)
                    page.keyboard.press('ArrowDown')
                    page.keyboard.press('Enter')
                fuel = page.locator('#_r_g_')
                if fuel.count() > 0:
                    page.evaluate("""() => {
                        const el = document.querySelector('#_r_g_');
                        if (el) el.click();
                    }""")
                else:
                    if page.get_by_text('Avgas').count() > 0:
                        page.get_by_text('Avgas').first.click()
                page.wait_for_timeout(500)
        # attempt to advance through any subsequent steps
        for step in range(3):
            next_button = page.locator('[data-gtm-id="create_aircraft_next"]')
            if next_button.count() > 0:
                fill_profile_step()
                page.evaluate("() => { const el = document.querySelector('[data-gtm-id=\"create_aircraft_next\"]'); if (el) el.click(); }")
                page.wait_for_timeout(5000)
                step_png = OUTPUT_PATH.parent / f'flysto_aircraft_setup_step{step+1}.png'
                step_html = OUTPUT_PATH.parent / f'flysto_aircraft_setup_step{step+1}.html'
                page.screenshot(path=str(step_png), full_page=True)
                step_html.write_text(page.content())
            else:
                break
        page.wait_for_timeout(5000)

        setup_button = page.get_by_role('button', name='Aircraft setup')
        if setup_button.count() > 0:
            setup_button.first.click()
            page.wait_for_timeout(4000)
        else:
            # fallback to banner link on logs page
            page.goto('https://www.flysto.net/logs', wait_until='load', timeout=60000)
            page.wait_for_timeout(3000)
            link = page.get_by_role('link', name='here')
            if link.count() > 0:
                link.first.click()
                page.wait_for_timeout(4000)

        # capture any pending request in case we don't reach the final step
        page.wait_for_timeout(2000)

        # select "New aircraft" if visible
        if page.get_by_text('New aircraft').count() > 0:
            page.get_by_text('New aircraft').first.click()
            page.wait_for_timeout(1000)

        # fill tail number (first input in modal)
        tail_input = page.locator('#_r_0_')
        if tail_input.count() > 0:
            tail_input.first.click()
            tail_input.first.fill('TEST-OTHER-UI')
            page.wait_for_timeout(500)

        # set model to Other using react-select combobox
        model_input = page.get_by_role('combobox')
        if model_input.count() > 0:
            model_input.first.click()
            page.wait_for_timeout(500)
            model_input.first.fill('Other')
            page.wait_for_timeout(500)
            page.keyboard.press('ArrowDown')
            page.keyboard.press('Enter')
            page.wait_for_timeout(500)

            # capture dropdown options if present
            options = page.locator('[role="option"]')
            option_texts = []
            if options.count() > 0:
                for i in range(min(30, options.count())):
                    try:
                        option_texts.append(options.nth(i).inner_text().strip())
                    except Exception:
                        continue
            options_path = OUTPUT_PATH.parent / 'flysto_aircraft_setup_options.json'
            if option_texts:
                options_path.write_text(json.dumps(option_texts, indent=2))

            option = page.get_by_role('option').filter(has_text='Other model')
            if option.count() > 0:
                option.first.click()
            else:
                page.keyboard.press('Enter')

        page.wait_for_timeout(1000)

        serial_input = page.locator('#_r_3_')
        if serial_input.count() > 0:
            serial_input.first.fill('SN-TEST')

        notes_input = page.locator('#_r_5_')
        if notes_input.count() > 0:
            notes_input.first.fill('skybridge test')

        # fill notes to ensure button enables
        notes_input = page.locator("input[placeholder*='Notes' i]")
        if notes_input.count() > 0:
            notes_input.first.fill('skybridge test')

        # click Next using data-gtm-id
        next_button = page.locator('[data-gtm-id="create_aircraft_next"]')
        if next_button.count() > 0:
            next_button.first.click(force=True)
        else:
            for label in ['Next', 'Save', 'Create']:
                button = page.get_by_role('button', name=label)
                if button.count() > 0:
                    button.first.click(force=True)
                    break


        # if advanced setup step appears, choose create profile and continue
        if page.get_by_text('How would you like to configure your aircraft model?').count() > 0:
            option = page.get_by_text('Create profile from scratch')
            if option.count() > 0:
                option.first.click()
            next_button = page.locator('[data-gtm-id="create_aircraft_next"]')
            if next_button.count() > 0:
                next_button.first.click(force=True)
            else:
                for label in ['Next', 'Save', 'Create']:
                    button = page.get_by_role('button', name=label)
                    if button.count() > 0:
                        if button.first.is_enabled():
                            button.first.click(force=True)
                        break
            page.wait_for_timeout(3000)

        # capture any request after profile step
        page.wait_for_timeout(2000)

        # helper to fill profile step if present
        def fill_profile_step() -> None:
            if page.get_by_text('Model name').count() > 0:
                model_name = page.locator('#_r_a_')
                if model_name.count() > 0:
                    model_name.first.fill('Other')
                vso = page.locator('#_r_c_')
                if vso.count() > 0:
                    vso.first.fill('40')
                engine_count = page.locator('#_r_j_')
                if engine_count.count() > 0:
                    engine_count.first.fill('1')
                cyl_count = page.locator('#_r_l_')
                if cyl_count.count() > 0:
                    cyl_count.first.fill('4')
                engine = page.get_by_role('combobox')
                if engine.count() > 0:
                    page.evaluate("""() => {
                        const el = document.querySelector('#react-select-3-input');
                        if (el) el.focus();
                    }""")
                    page.wait_for_timeout(300)
                    page.keyboard.press('ArrowDown')
                    page.keyboard.press('Enter')
                fuel = page.locator('#_r_g_')
                if fuel.count() > 0:
                    page.evaluate("""() => {
                        const el = document.querySelector('#_r_g_');
                        if (el) el.click();
                    }""")
                else:
                    if page.get_by_text('Avgas').count() > 0:
                        page.get_by_text('Avgas').first.click()
                page.wait_for_timeout(500)
        # attempt to advance through any subsequent steps
        for step in range(3):
            next_button = page.locator('[data-gtm-id="create_aircraft_next"]')
            if next_button.count() > 0:
                fill_profile_step()
                page.evaluate("() => { const el = document.querySelector('[data-gtm-id=\"create_aircraft_next\"]'); if (el) el.click(); }")
                page.wait_for_timeout(5000)
                step_png = OUTPUT_PATH.parent / f'flysto_aircraft_setup_step{step+1}.png'
                step_html = OUTPUT_PATH.parent / f'flysto_aircraft_setup_step{step+1}.html'
                page.screenshot(path=str(step_png), full_page=True)
                step_html.write_text(page.content())
            else:
                break
        page.wait_for_timeout(5000)


        state = {
            'tail_value': page.locator('#_r_0_').input_value() if page.locator('#_r_0_').count() > 0 else None,
            'serial_value': page.locator('#_r_3_').input_value() if page.locator('#_r_3_').count() > 0 else None,
            'notes_value': page.locator('#_r_5_').input_value() if page.locator('#_r_5_').count() > 0 else None,
            'model_text': None,
            'buttons': [],
        }
        try:
            model_text = page.locator('div[role="dialog"] [aria-haspopup="true"]').inner_text()
            state['model_text'] = model_text
        except Exception:
            pass
        for label in ['Next', 'Save', 'Create']:
            button = page.get_by_role('button', name=label)
            if button.count() > 0:
                state['buttons'].append({'label': label, 'enabled': button.first.is_enabled()})
        state_path = OUTPUT_PATH.parent / 'flysto_aircraft_setup_state.json'
        state_path.write_text(json.dumps(state, indent=2))
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(captured or {'error': 'no request captured'}, indent=2))
        ALL_PATH.write_text(json.dumps(all_requests, indent=2))
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        html_path = OUTPUT_PATH.parent / 'flysto_aircraft_setup.html'
        html_path.write_text(page.content())

        # save storage state for manual inspection
        state_path = OUTPUT_PATH.parent / 'flysto_storage_state.json'
        state_path.write_text(json.dumps(context.storage_state(), indent=2))
        browser.close()


if __name__ == '__main__':
    main()
