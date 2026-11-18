# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""The one place that hands a person from Iris to the room.

This module applies the chosen iframe decision. Browsers
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

# The chosen decision.
# HANDOFF_MODE is iframe, iframe-except or redirect. REDIRECT_BROWSERS_TEXT is
# the comma list of browsers to redirect (or "none"). A unit test pins both
# values, so changing one is a deliberate edit.
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


def detect_brave(window):
    """True when `window` is Brave. False when it is not, or the check is absent.

    Brave's user agent is plain Chrome, so only `navigator.brave.isBrave()` tells
    it apart. That call returns a Promise, which anvil.js awaits for us. Never
    raises: any failure means "not Brave", so the iframe stays the default.
    """
    try:
        brave = window.navigator.brave
        if brave is None:
            return False
        return bool(brave.isBrave())
    except Exception:
        return False


def method_for(user_agent, max_touch_points=0, is_brave=False):
    """The method the recorded decision gives for this browser.

    Brave always redirects, whatever the decision says: its Shields block the
    third-party storage the room needs inside an iframe, which makes the room
    ask for the name again. This is a rule beside the decision, not a token in
    the closed vocabulary, because a user agent cannot show it.
    """
    if is_brave:
        return "redirect"
    return choose(
        HANDOFF_MODE, REDIRECT_BROWSERS, classify(user_agent, max_touch_points)
    )


def start(url, frame=None, user_agent=None, max_touch_points=0, is_brave=False):
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
            is_brave = detect_brave(window)
        method = method_for(user_agent, max_touch_points, is_brave)
    if method == "iframe" and frame is not None:
        frame.src = url
        return "iframe"
    from anvil.js import window

    window.location.href = url
    return "redirect"
