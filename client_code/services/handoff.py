"""The one place that hands a person from Iris to the room.

This module applies the recorded iframe decision (02-SPIKE-RESULTS.md). Browsers
that get the embed see the room inside the Iris page, with the short link still
in the address bar. Every other browser is sent to the address by a top-level
redirect. The address is always the one `join.join_url` built from the server
reply, and it is refused unless it is http or https.

Loads on both sides, so `anvil.js` is imported inside the functions that need it.
"""

from iris.services import join  # pyright: ignore[reportAttributeAccessIssue]

# The closed vocabulary for the `Redirect browsers:` line. `classify` may also
# return "other", which is not a configurable token.
BROWSER_TOKENS = (
    "chrome",
    "firefox",
    "edge",
    "safari-macos",
    "safari-ios",
    "chrome-android",
    "in-app",
)

# Lower-case substrings of in-app browsers. Best effort: an unlisted in-app
# browser falls to the browser it imitates.
IN_APP_MARKERS = (
    "fban",
    "fbav",
    "fb_iab",
    "instagram",
    " line/",
    "micromessenger",
    "snapchat",
    "linkedinapp",
    "twitter",
    "musical_ly",
    "pinterest",
    "gsa/",
    "; wv)",
)

MODES = ("iframe", "iframe-except", "redirect")

# The recorded decision, from the Decisions block of 02-SPIKE-RESULTS.md.
# HANDOFF_MODE is iframe, iframe-except or redirect. REDIRECT_BROWSERS_TEXT is
# the comma list from `Redirect browsers:` (or "none"). A unit test fails if
# either differs from that file.
HANDOFF_MODE = "iframe-except"
REDIRECT_BROWSERS_TEXT = "safari-ios, in-app"


def _touch_count(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def classify(user_agent, max_touch_points=0):
    """Name the browser: one of BROWSER_TOKENS, or "other". Never raises."""
    if not isinstance(user_agent, str):
        return "other"
    text = user_agent.lower()
    for marker in IN_APP_MARKERS:
        if marker in text:
            return "in-app"
    # Every iOS browser is WebKit. An iPad in desktop mode says Macintosh.
    if "iphone" in text or "ipad" in text or "ipod" in text:
        return "safari-ios"
    if "macintosh" in text and _touch_count(max_touch_points) > 1:
        return "safari-ios"
    return _classify_engine(text)


def _classify_engine(text):
    """Classify a lower-case user agent that is not in-app and not iOS."""
    if "edg/" in text or "edga/" in text:
        return "edge"
    if "firefox/" in text:
        return "firefox"
    chromium = "chrome/" in text or "chromium/" in text
    if "android" in text and "chrome/" in text:
        return "chrome-android"
    if "macintosh" in text and "safari/" in text and not chromium:
        return "safari-macos"
    if chromium or "crios/" in text:
        return "chrome"
    return "other"


def parse_redirect_browsers(text):
    """Read the `Redirect browsers:` list into a tuple of tokens.

    "none" or an empty text gives (). A word outside BROWSER_TOKENS raises
    ValueError, so a typo stops the build instead of being guessed.
    """
    if text is None:
        return ()
    words = [word.strip().lower() for word in str(text).split(",")]
    words = [word for word in words if word != ""]
    if words == ["none"]:
        return ()
    found = []
    for word in words:
        if word not in BROWSER_TOKENS:
            raise ValueError(
                "Redirect browsers word '"
                + word
                + "' is not one of: "
                + ", ".join(BROWSER_TOKENS)
            )
        if word not in found:
            found.append(word)
    return tuple(found)


def choose(mode, redirect_browsers, browser):
    """Return "iframe" or "redirect" for a browser token under `mode`."""
    if mode == "iframe":
        return "iframe"
    if mode == "redirect":
        return "redirect"
    if mode == "iframe-except":
        if browser == "other" or browser in redirect_browsers:
            return "redirect"
        return "iframe"
    raise ValueError("Unknown hand-off mode: " + str(mode))


REDIRECT_BROWSERS = parse_redirect_browsers(REDIRECT_BROWSERS_TEXT)


def method_for(user_agent, max_touch_points=0):
    """The method the recorded decision gives for this browser."""
    return choose(
        HANDOFF_MODE, REDIRECT_BROWSERS, classify(user_agent, max_touch_points)
    )


def start(url, frame=None, user_agent=None, max_touch_points=0):
    """Open the room at `url`: in `frame` when the decision says so, else by redirect.

    `url` must be an http or https address. Returns "iframe" or "redirect".
    """
    if not join.is_http_url(url):
        raise ValueError("Not a web address.")
    if frame is None:
        method = "redirect"
    else:
        if user_agent is None:
            # Imported here so this module also loads on the server.
            from anvil.js import window

            user_agent = window.navigator.userAgent
            max_touch_points = _touch_count(window.navigator.maxTouchPoints)
        method = method_for(user_agent, max_touch_points)
    if method == "iframe" and frame is not None:
        frame.src = url
        return "iframe"
    from anvil.js import window

    window.location.href = url
    return "redirect"
