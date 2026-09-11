"""Browser verification against a running local dashboard; optional real live demo.

python -m frontend.test_browser [--live]
Requires the optional Playwright test dependency and installed Microsoft Edge.
"""

import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "results"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors, outbound = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: outbound.append(request.url)
                if not request.url.startswith(("http://127.0.0.1:8787/", "data:")) else None)
        page.goto("http://127.0.0.1:8787/")
        page.wait_for_selector("#attack-rows tr", timeout=15000)
        assert page.locator("#attack-rows tr").count() == 20
        assert "33.33%" in page.locator("#metrics").inner_text()
        page.screenshot(path=str(root / "dashboard_desktop.png"), full_page=True)
        page.select_option("#category-filter", "tool_misuse")
        page.select_option("#result-filter", "COMPROMISED")
        assert page.locator("#attack-rows tr").count() == 3
        page.locator('[data-detail="TM-001"]').first.click()
        page.wait_for_selector("dialog[open]")
        assert "TP-CONF-IR-2026-9F3C" in page.locator("#detail-content").inner_text()
        assert "COMPROMISED" in page.locator("#detail-content").inner_text()
        assert "BLOCKED" in page.locator("#detail-content").inner_text()
        page.screenshot(path=str(root / "dashboard_evidence.png"))
        page.keyboard.press("Escape")
        page.click("#clear-filters")
        page.select_option("#severity-filter", "LOW")
        assert page.locator("#empty-table").is_visible()
        page.click("#clear-filters")
        # Rendering untrusted output must not execute HTML or trigger beacons.
        assert page.evaluate("esc('<img src=https://untrusted.example onerror=alert(1)>')").startswith("&lt;img")
        page.set_viewport_size({"width": 390, "height": 844})
        page.evaluate("window.scrollTo(0,0)")
        page.screenshot(path=str(root / "dashboard_mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile page overflows"
        if args.live:
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.select_option("#demo-attack", "TM-001")
            for mode, verdict in (("baseline", "COMPROMISED"), ("defended", "BLOCKED")):
                page.click(f"#run-{mode}")
                page.wait_for_function("document.querySelector('#live-status').textContent.includes('Fresh evidence saved')", timeout=195000)
                assert verdict in page.locator("#live-status").inner_text(), page.locator("#live-status").inner_text()
            page.screenshot(path=str(root / "dashboard_live.png"), full_page=True)
        assert not errors, errors
        assert not outbound, outbound
        browser.close()
    print("Browser checks passed: desktop/mobile, filters, details, safe text, no external requests" + (", live baseline/defended" if args.live else ""))


if __name__ == "__main__":
    main()
