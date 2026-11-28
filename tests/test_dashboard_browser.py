"""Real Chromium smoke tests for the responsive Streamlit UI.

The subprocess receives a test-only sitecustomize shim that supplies read-only
fake log records. Browser traffic is restricted to the local Streamlit server.
"""
from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _write_test_sitecustomize(path: Path) -> None:
    path.write_text(
        """
from datetime import datetime, timedelta, timezone
import jarvis_common

_now = datetime.now(timezone.utc)
_ROWS = [
    {"module": "chat", "level": "info", "message": "chat_request", "created_at": (_now - timedelta(minutes=4)).isoformat()},
    {"module": "chat", "level": "info", "message": "chat_response", "created_at": (_now - timedelta(minutes=3)).isoformat()},
    {"module": "email_sender", "level": "error", "message": "delivery_failure", "created_at": (_now - timedelta(minutes=2)).isoformat()},
    {"module": "follow_up", "level": "warning", "message": "followup_pending", "created_at": (_now - timedelta(minutes=1)).isoformat()},
]
class _Query:
    def __init__(self, rows):
        self.rows = rows
    def select(self, *_args, **_kwargs): return self
    def gte(self, *_args, **_kwargs): return self
    def lte(self, *_args, **_kwargs): return self
    def order(self, *_args, **_kwargs): return self
    def limit(self, *_args, **_kwargs): return self
    def execute(self):
        from types import SimpleNamespace
        return SimpleNamespace(data=list(self.rows))
class _DB:
    def table(self, name):
        return _Query(_ROWS if name == "logs" else [])
jarvis_common.get_service_supabase = lambda: _DB()
jarvis_common.generate_text = lambda *_args, **_kwargs: "BROWSER_CHAT_RESPONSE"
jarvis_common.log_event = lambda *_args, **_kwargs: True
jarvis_common.audit_event = lambda *_args, **_kwargs: True
jarvis_common.get_model_name = lambda: "browser-test-model"
jarvis_common.estimate_response_tokens = lambda *_args, **_kwargs: 256
import global_lead_research
global_lead_research.get_research_market = lambda _db: "Hungary"
import jarvis_memory
jarvis_memory.memory_command = lambda _prompt: ("", None)
jarvis_memory.get_memories = lambda *_args, **_kwargs: []
""".lstrip(),
        encoding="utf-8",
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.parametrize("browser_name", ["chromium", "firefox", "webkit"])
@pytest.mark.browser_e2e
def test_cross_browser_responsive_dashboard_and_analytics_interactions(tmp_path, monkeypatch, browser_name):
    playwright = pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    from plotly.offline import get_plotlyjs

    shim_dir = tmp_path / "python-shim"
    shim_dir.mkdir()
    _write_test_sitecustomize(shim_dir / "sitecustomize.py")

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update({
        "JARVIS_DASHBOARD_PASSWORD": "browser-test-password",
        "STREAMLIT_SERVER_HEADLESS": "true",
        "STREAMLIT_SERVER_FILE_WATCHER_TYPE": "none",
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        "PYTHONPATH": os.pathsep.join([str(shim_dir), str(ROOT), env.get("PYTHONPATH", "")]),
    })
    server_log = tmp_path / "streamlit.log"
    with server_log.open("w", encoding="utf-8") as output:
        server = subprocess.Popen(
            [
                sys.executable, "-m", "streamlit", "run", str(ROOT / "dashboard.py"),
                "--server.address", "127.0.0.1",
                "--server.port", str(port),
                "--server.headless", "true",
                "--browser.gatherUsageStats", "false",
            ],
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 45
            ready = False
            while time.monotonic() < deadline and server.poll() is None:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                        ready = True
                        break
                except OSError:
                    time.sleep(0.25)
            assert ready, f"Streamlit did not start. Log: {server_log.read_text(encoding='utf-8')}"

            screenshot_root = Path(os.getenv("JARVIS_BROWSER_ARTIFACT_DIR", str(tmp_path / "screenshots")))
            screenshot_dir = screenshot_root / browser_name
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            with sync_playwright() as runtime:
                browser = getattr(runtime, browser_name).launch(headless=True)
                context = browser.new_context(
                    viewport={"width": 1440, "height": 960},
                    device_scale_factor=1,
                    service_workers="block",
                )
                page = context.new_page()
                local_plotly_js = get_plotlyjs()

                failed_requests = []
                page.on("requestfailed", lambda request: failed_requests.append(
                    (request.url, request.failure)
                ))

                def route_without_external_network(route):
                    request_url = route.request.url
                    parsed_url = urlparse(request_url)
                    is_local_server = (
                        parsed_url.scheme in {"http", "https"}
                        and parsed_url.hostname in {"127.0.0.1", "localhost", "::1"}
                        and parsed_url.port == port
                    )
                    if is_local_server:
                        route.continue_()
                    elif "plotly" in request_url.casefold() and ".js" in request_url.casefold():
                        # Streamlit's chart bundle may request Plotly.js from a CDN.
                        # Fulfil it from the already-installed local Python package.
                        route.fulfill(status=200, content_type="application/javascript", body=local_plotly_js)
                    else:
                        route.abort()

                page.route("**/*", route_without_external_network)
                page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
                login_password = page.get_by_label("Dashboard jelszó")
                login_password.wait_for(state="visible", timeout=30000)
                login_heading = page.get_by_role("heading", name="JARVIS")
                login_heading.wait_for(state="visible", timeout=30000)
                login_button = page.get_by_role("button", name="Belépés")
                login_button.wait_for(state="visible", timeout=30000)
                assert login_password.is_visible() and login_button.is_visible()
                page.screenshot(path=str(screenshot_dir / "login-desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                page.wait_for_timeout(250)
                password_box = login_password.bounding_box()
                button_box = login_button.bounding_box()
                assert password_box is not None and 0 <= password_box["x"] and password_box["x"] + password_box["width"] <= 390, ("mobile login password field overflows viewport", password_box)
                assert button_box is not None and 0 <= button_box["x"] and button_box["x"] + button_box["width"] <= 390, ("mobile login button overflows viewport", button_box)
                page.screenshot(path=str(screenshot_dir / "login-mobile.png"), full_page=True)
                page.set_viewport_size({"width": 320, "height": 720})
                page.wait_for_timeout(250)
                small_password_box = login_password.bounding_box()
                small_button_box = login_button.bounding_box()
                assert small_password_box is not None and 0 <= small_password_box["x"] and small_password_box["x"] + small_password_box["width"] <= 320, ("small-mobile login password field overflows viewport", small_password_box)
                assert small_button_box is not None and 0 <= small_button_box["x"] and small_button_box["x"] + small_button_box["width"] <= 320, ("small-mobile login button overflows viewport", small_button_box)
                page.screenshot(path=str(screenshot_dir / "login-small-mobile.png"), full_page=True)
                page.set_viewport_size({"width": 1440, "height": 960})
                page.wait_for_timeout(250)
                login_password.fill("browser-test-password")
                page.get_by_role("button", name="Belépés").click()
                page.get_by_text("Üdvözöllek!").wait_for(timeout=30000)

                chat_input = page.get_by_placeholder("Írj üzenetet a JARVIS-nak...")
                chat_input.fill("Szia JARVIS, böngészős ellenőrzés.")
                chat_input.press("Enter")
                page.get_by_text("BROWSER_CHAT_RESPONSE").wait_for(timeout=30000)
                page.screenshot(path=str(screenshot_dir / "chat-desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                page.wait_for_timeout(350)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_function("window.scrollY === 0")
                assert page.locator('[data-testid="stChatInput"]').is_visible()
                welcome_heading = page.locator(".jarvis-welcome h1")
                welcome_heading.wait_for(state="visible", timeout=10000)
                page.evaluate("window.scrollTo(0, 0)")
                heading_box = welcome_heading.bounding_box()
                heading_metrics = page.evaluate("""() => {
                    const heading = document.querySelector(".jarvis-welcome h1");
                    const welcome = heading?.closest(".jarvis-welcome");
                    const style = heading ? getComputedStyle(heading) : null;
                    const parentStyle = welcome ? getComputedStyle(welcome) : null;
                    const rect = heading?.getBoundingClientRect();
                    return {
                        innerWidth: window.innerWidth,
                        headingMarginTop: style?.marginTop,
                        welcomePaddingTop: parentStyle?.paddingTop,
                        documentTop: rect ? rect.top + window.scrollY : null
                    };
                }""")
                page.screenshot(path=str(screenshot_dir / "chat-mobile.png"), full_page=True)
                assert heading_box is not None and heading_box["y"] >= 96, ("mobile welcome heading overlaps Streamlit header", heading_box, heading_metrics)
                assert heading_box["x"] >= 0 and heading_box["x"] + heading_box["width"] <= 390, ("mobile welcome heading overflows viewport", heading_box, heading_metrics)
                page.set_viewport_size({"width": 320, "height": 720})
                page.wait_for_timeout(350)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_function("window.scrollY === 0")
                page.evaluate("window.scrollTo(0, 0)")
                small_mobile_box = welcome_heading.bounding_box()
                page.screenshot(path=str(screenshot_dir / "chat-small-mobile.png"), full_page=True)
                assert small_mobile_box is not None and small_mobile_box["y"] >= 96, ("small-mobile welcome heading overlaps Streamlit header", small_mobile_box)
                assert small_mobile_box is not None and small_mobile_box["x"] >= 0 and small_mobile_box["x"] + small_mobile_box["width"] <= 320, ("small-mobile welcome heading overflows viewport", small_mobile_box)
                page.set_viewport_size({"width": 1440, "height": 960})
                page.wait_for_timeout(350)

                page.get_by_role("button", name="Analitika").click()
                page.get_by_text("Naplózott aktivitási trend").wait_for(timeout=30000)
                try:
                    page.wait_for_function(
                        "document.querySelectorAll('[data-testid=stPlotlyChart]').length === 4",
                        timeout=20000,
                    )
                except Exception as exc:
                    raise AssertionError(
                        f"Plotly did not render; failed requests={failed_requests}; "
                        f"server log={server_log.read_text(encoding='utf-8')[-4000:]}"
                    ) from exc
                page.screenshot(path=str(screenshot_dir / "analytics-debug.png"), full_page=True)
                assert not page.locator('[data-testid="stChatInput"]').is_visible()
                chart_count = page.locator('[data-testid="stPlotlyChart"]').count()
                if chart_count != 4:
                    testids = page.locator("[data-testid]").evaluate_all(
                        "(nodes) => nodes.map(node => node.getAttribute('data-testid')).filter(value => /chart|plot/i.test(value || ''))"
                    )
                    raise AssertionError(
                        f"Expected 4 Plotly charts, got {chart_count}; "
                        f"chart testids={testids}; body={page.locator('body').inner_text()[-3000:]}; "
                        f"server log={server_log.read_text(encoding='utf-8')[-3000:]}"
                    )
                page.get_by_text("7 nap", exact=True).click()
                page.wait_for_timeout(500)
                assert page.locator('[data-testid="stPlotlyChart"]').count() == 4

                viewports = [
                    ("desktop", 1440, 960),
                    ("laptop", 1024, 768),
                    ("tablet", 768, 1024),
                    ("mobile", 390, 844),
                    ("small-mobile", 320, 720),
                ]
                for label, width, height in viewports:
                    page.set_viewport_size({"width": width, "height": height})
                    page.wait_for_timeout(350)
                    dimensions = page.evaluate(
                        """() => {
                            const main = document.querySelector('[data-testid="stMain"]');
                            const charts = [...document.querySelectorAll('[data-testid="stPlotlyChart"]')];
                            return {
                                viewport: window.innerWidth,
                                mainClient: main ? main.clientWidth : 0,
                                mainScroll: main ? main.scrollWidth : 0,
                                chartWidths: charts.map(chart => Math.round(chart.getBoundingClientRect().width)),
                                kpiWidths: [...document.querySelectorAll('.jarvis-kpi')].map(card => Math.round(card.getBoundingClientRect().width)),
                                chartCount: charts.length
                            };
                        }"""
                    )
                    page.screenshot(path=str(screenshot_dir / f"analytics-{label}.png"), full_page=True)
                    assert dimensions["chartCount"] == 4, (label, dimensions)
                    assert dimensions["mainScroll"] <= dimensions["mainClient"] + 2, (label, dimensions)
                    assert all(0 < chart_width <= dimensions["mainClient"] + 2 for chart_width in dimensions["chartWidths"]), (label, dimensions)
                    assert len(dimensions["kpiWidths"]) == 5 and min(dimensions["kpiWidths"]) >= 180, (label, dimensions)

                context.close()
                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
