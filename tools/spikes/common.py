"""Helpers the spike probes share. Imported by name from tools/spike.py's path.

Heavy packages (playwright, anvil.server) are imported inside the functions that
need them, so this module is cheap to import.
"""

import contextlib
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

UPLINK_KEY = "dev-uplink"
FIRST_LOAD_TIMEOUT_MS = 120_000
LOAD_TIMEOUT_MS = 60_000


def uplink_url(base_url: str) -> str:
    """The uplink websocket URL on the same host and port as base_url."""
    parts = urlparse(base_url)
    return f"ws://{parts.hostname}:{parts.port or 80}/_/uplink"


@contextlib.contextmanager
def uplink(base_url: str):
    """Connect the dev uplink for the block and always disconnect.

    anvil-uplink retries a dropped connection on a non-daemon thread, which
    would keep the probe alive, so reconnecting is turned off.
    """
    import anvil.server

    anvil.server.reconnect = lambda closed_connection: None
    anvil.server.connect(UPLINK_KEY, url=uplink_url(base_url))
    try:
        yield anvil.server
    finally:
        anvil.server.disconnect()


def proxy_settings():
    """A Playwright proxy dict when the environment names one, else None.

    Loopback is proxied too, for hosts that can only reach localhost that way.
    """
    server = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if not server:
        return None
    return {"server": server, "bypass": "<-loopback>"}


@contextlib.contextmanager
def browser(**launch):
    """A headless chromium for the block."""
    from playwright.sync_api import sync_playwright

    proxy = proxy_settings()
    if proxy and "proxy" not in launch:
        launch["proxy"] = proxy
    with sync_playwright() as p:
        chromium = p.chromium.launch(**launch)
        try:
            yield chromium
        finally:
            chromium.close()


def http_get(url: str, timeout: int = 30):
    """GET without following redirects' failures: returns (status, headers, body)."""
    request = urllib.request.Request(url, headers={"User-Agent": "iris-spike"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, body
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", "replace")
        return err.code, {k.lower(): v for k, v in err.headers.items()}, body


def banner_visible(page) -> bool:
    """True when the Anvil error banner is showing (it is hidden otherwise)."""
    return page.get_by_text("This app has experienced an error").first.is_visible()


def banner_detail(page) -> str:
    """The text behind the error banner, or "" when it is not showing.

    Clicking the banner opens the error message and traceback.
    """
    if not banner_visible(page):
        return ""
    try:
        page.get_by_text("Click for more information").first.click(timeout=5000)
        page.wait_for_timeout(500)
        return " ".join(page.evaluate("document.body.innerText").split())[:600]
    except Exception as exc:
        return f"(could not open banner: {type(exc).__name__})"


ERROR_TEXT = "This app has experienced an error"


def watch(page) -> list:
    """Collect the page's console errors and uncaught errors as it runs."""
    seen: list = []
    page.on(
        "console", lambda m: seen.append(m.text[:200]) if m.type == "error" else None
    )
    page.on("pageerror", lambda e: seen.append(f"pageerror {str(e)[:200]}"))
    return seen


def wait_for_text(page, expect: str, timeout: int, seen: list):
    """Wait for expect in the page text. Returns None, or a short error string.

    Gives up early when the Anvil error banner shows, and says what the page
    and console showed, so a failure is diagnosable from the evidence alone.
    """
    try:
        page.wait_for_function(
            "([want, bad]) => { const t = document.body.innerText; "
            "return t.includes(want) || t.includes(bad); }",
            arg=[expect, ERROR_TEXT],
            timeout=timeout,
        )
    except Exception as exc:
        return f"{type(exc).__name__}: {str(exc).splitlines()[0][:100]}"
    text = page.evaluate("document.body.innerText")
    if expect in text:
        return None
    return f"error banner; page text {text[:300]!r}; console {seen[:4]}"
