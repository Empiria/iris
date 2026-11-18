"""Point Playwright at the repo's browser cache, and provide the dev accounts.

`just setup` installs chromium into the git-ignored `.anvil/ms-playwright`, so a
bare `uv run pytest tests/e2e` finds the same browser whatever HOME is. An
explicit PLAYWRIGHT_BROWSERS_PATH still wins.

`staff_login` and `non_staff_login` return `(email, password)` for the two local
dev accounts. The first runs `tools/create_staff.py --dev`, which makes both and
is safe to run again, so a second run in the same database passes.

The stack's host port comes from IRIS_PORT (default 3030), like the justfile's
`port` setting. There is no `base_url` in pyproject.toml: the `base_url` fixture
below reads `--base-url`, then IRIS_URL, then IRIS_PORT.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from playwright.sync_api import expect

FIRST_LOAD_MS = 120_000
VISIBLE_MS = 30_000
UPLINK_CONNECT_S = 30

ROOT = Path(__file__).resolve().parents[2]
BROWSERS = ROOT / ".anvil" / "ms-playwright"
LAUNCHER = ROOT / "tools" / "create_staff.py"

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS))


def _launcher_constants():
    """Load the launcher by path to read its DEV_* constants (no anvil import)."""
    spec = importlib.util.spec_from_file_location("iris_create_staff", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def base_url(request):
    """The app URL: an explicit --base-url, else IRIS_URL, else the stack port."""
    return request.config.getoption("base_url") or _launcher_constants().base_url(
        os.environ
    )


@pytest.fixture(scope="session")
def staff_login():
    dev = _launcher_constants()
    result = subprocess.run(
        [sys.executable, str(LAUNCHER), "--dev"],
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"create_staff --dev failed:\n{result.stderr}")
    return dev.DEV_STAFF_EMAIL, dev.DEV_STAFF_PASSWORD


@pytest.fixture(scope="session")
def non_staff_login(staff_login):
    dev = _launcher_constants()
    return dev.DEV_VIEWER_EMAIL, dev.DEV_VIEWER_PASSWORD


@pytest.fixture
def staff_page(browser, base_url, staff_login):
    """A signed-in staff page on /staff, in its own context with clipboard access."""
    email, password = staff_login
    context = browser.new_context(
        base_url=base_url, permissions=["clipboard-read", "clipboard-write"]
    )
    try:
        page = context.new_page()
        page.goto("staff", wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)
        expect(page.get_by_role("heading", name="Staff sign-in")).to_be_visible(
            timeout=FIRST_LOAD_MS
        )
        page.get_by_label("Email").fill(email)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_text("Signed in as")).to_be_visible(timeout=VISIBLE_MS)
        yield page
    finally:
        context.close()


@pytest.fixture(scope="session")
def uplink():
    """An anonymous-by-session `anvil.server` uplink connection to the local stack.

    Same URL and key rules as tools/dev_seed.py. Connects in a daemon thread
    with a timeout, because a connect to a stack that is down can hang.
    """
    import threading

    import anvil.server

    url = _launcher_constants().uplink_url(os.environ)
    key = os.environ.get("IRIS_UPLINK_KEY", "dev-uplink")
    # The uplink retries a dropped connection on a non-daemon thread, which would
    # keep the test process alive after the run.
    anvil.server.reconnect = lambda closed_connection: None
    errors = []

    def connect():
        try:
            anvil.server.connect(key, url=url)
        except Exception as error:
            errors.append(type(error).__name__)

    thread = threading.Thread(target=connect, daemon=True)
    thread.start()
    thread.join(timeout=UPLINK_CONNECT_S)
    if thread.is_alive() or errors:
        pytest.fail(f"could not connect the uplink to {url} ({errors or 'timeout'})")
    try:
        yield anvil.server
    finally:
        anvil.server.disconnect()
