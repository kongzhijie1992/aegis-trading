"""Headless checks of the real dashboard on desktop and mobile layouts."""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from trading_monitoring.dashboard import DashboardStore, demo_snapshot, start_server


def main():
    with tempfile.TemporaryDirectory() as folder:
        store = DashboardStore(Path(folder) / "ui.sqlite")
        for i in range(10):
            data = demo_snapshot()
            data["as_of"] = (datetime.now(UTC) - timedelta(minutes=9 - i)).isoformat()
            data["net_liquidation"] -= (9 - i) * 10
            store.update(data)
        live_store = DashboardStore(Path(folder) / "live.sqlite")
        live_store.update(
            {
                **demo_snapshot(),
                "mode": "live",
                "account": "U123",
                "positions": [],
                "net_liquidation": None,
                "status": "not_configured",
                "error": "Real account is not configured",
            }
        )
        server = start_server(store, 0, environments={"paper": store, "live": live_store})
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}")
                page.wait_for_function(
                    "document.querySelector('#mode').textContent.includes('DEMO')"
                )
                assert page.locator("#positions tr").count() == 2
                assert page.locator("#chart svg").count() == 1
                page.get_by_role("button", name="Real", exact=True).click()
                expect(page.locator("#mode")).to_contain_text("REAL MONEY")
                expect(page.locator("#notice")).to_contain_text("not configured")
                expect(page.locator("#nav")).to_have_text("—")
                assert "SPY" not in page.locator("#positions").inner_text()
                page.get_by_role("button", name="Paper", exact=True).click()
                expect(page.locator("#mode")).to_contain_text("DEMO")
                expect(page.locator("#positions")).to_contain_text("SPY")
                page.get_by_label("Search positions").fill("QQQ")
                assert page.locator("#positions tr").count() == 1
                with page.expect_download() as download:
                    page.get_by_role("button", name="Export positions").click()
                assert download.value.suggested_filename == "aegis-demo-positions.csv"
                page.get_by_label("Search positions").fill("")
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    "Mobile page overflows"
                )
                page.screenshot(path="dist/dashboard-mobile.png", full_page=True)
                page.set_viewport_size({"width": 1440, "height": 1000})
                page.screenshot(path="dist/dashboard-desktop.png", full_page=True)
                store.fail("Fixture disconnect")
                page.get_by_role("button", name="Refresh", exact=False).click()
                expect(page.locator("#notice")).to_contain_text("STALE")
                assert page.locator("#positions tr").count() == 2
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
    print(
        "Dashboard UI passed: render, chart, search, CSV download, mobile layout and stale-state preservation."
    )


if __name__ == "__main__":
    Path("dist").mkdir(exist_ok=True)
    main()
