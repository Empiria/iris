"""H1: the iframe browser matrix. Hosted and run by hand, so nothing is probed.

Assemble it with `just spike iframe_matrix --assemble-only`, push the printed
directory to a scratch Anvil app and open the app root in each browser. With
`--with-stack` the page is also loaded here, to check that it renders and that
the iframe carries the attributes the room needs.
"""

from common import FIRST_LOAD_TIMEOUT_MS, banner_detail, browser, watch

NEEDS_STACK = False

ALLOW = "camera; microphone; autoplay; display-capture"
REFERRER = "strict-origin-when-cross-origin"


def run(base_url):
    if not base_url:
        return [
            (
                "H1",
                "NOT RUN",
                "Owen-run overlay: assemble with --assemble-only, test by hand",
            )
        ]
    root = base_url.rstrip("/")
    page = None
    seen = []
    try:
        with browser() as chromium:
            page = chromium.new_context().new_page()
            seen = watch(page)
            page.goto(
                f"{root}/",
                wait_until="domcontentloaded",
                timeout=FIRST_LOAD_TIMEOUT_MS,
            )
            page.wait_for_selector(
                "iframe", state="attached", timeout=FIRST_LOAD_TIMEOUT_MS
            )
            room = page.input_value("input")
            page.get_by_role("button", name="Join").click()
            frame = page.locator("iframe")
            attrs = {
                "allow": frame.get_attribute("allow"),
                "referrerpolicy": frame.get_attribute("referrerpolicy"),
                "allowfullscreen": frame.get_attribute("allowfullscreen") is not None,
                "src": frame.get_attribute("src"),
            }
    except Exception as exc:
        banner = banner_detail(page) if page else ""
        return [
            (
                "H1",
                "FAIL",
                f"local render failed: {type(exc).__name__}: "
                f"{str(exc).splitlines()[0][:120]}; banner {banner}; "
                f"console {seen[:4]}",
            )
        ]
    ok = (
        len(room) == 12
        and room.isalpha()
        and room.islower()
        and attrs["allow"] == ALLOW
        and attrs["referrerpolicy"] == REFERRER
        and attrs["allowfullscreen"]
        and attrs["src"] == f"https://vdo.ninja/?room={room}&label=Matrix"
    )
    return [
        (
            "H1",
            "PASS" if ok else "FAIL",
            f"local render only, not a browser matrix: room {room!r}, iframe {attrs}",
        )
    ]
