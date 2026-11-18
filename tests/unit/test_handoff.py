# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Browser classification and the iframe-or-redirect hand-off.

`handoff.py` applies a fixed iframe decision. These tests pin the closed
browser vocabulary, the truth table of `choose`, and that the two constants in
the module agree with the values pinned here.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
# The hand-off Iris ships with. Pinned so a change is a deliberate edit.
PINNED_MODE = "iframe-except"
PINNED_REDIRECT_BROWSERS = "safari-ios, in-app"
HANDOFF_SOURCE = ROOT / "client_code" / "services" / "handoff.py"

WINDOWS_CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
LINUX_HEADLESS_CHROME = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) HeadlessChrome/120.0.0.0 Safari/537.36"
)
WINDOWS_EDGE = WINDOWS_CHROME + " Edg/120.0.0.0"
ANDROID_EDGE = (
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 EdgA/120.0.0.0"
)
DESKTOP_FIREFOX = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
)
ANDROID_FIREFOX = "Mozilla/5.0 (Android 14; Mobile; rv:121.0) Gecko/121.0 Firefox/121.0"
MACOS_SAFARI = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.1 Safari/605.1.15"
)
IPHONE_SAFARI = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
)
IPHONE_CHROME = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) CriOS/120.0.6099.119 Mobile/15E148 Safari/604.1"
)
IPHONE_FIREFOX = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) FxiOS/121.0 Mobile/15E148 Safari/605.1.15"
)
ANDROID_CHROME = (
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
ANDROID_WEBVIEW = (
    "Mozilla/5.0 (Linux; Android 10; K; wv) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Version/4.0 Chrome/120.0.0.0 Mobile Safari/537.36"
)
FACEBOOK_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 [FBAN/FBIOS;FBAV/430.0.0.0;FBDV/iPhone14,2]"
)
INSTAGRAM_ANDROID = ANDROID_CHROME + " Instagram 300.0.0.0 Android (29/10)"
LINE_APP = ANDROID_CHROME + " Line/13.0.0"
WECHAT = ANDROID_CHROME + " MicroMessenger/8.0.0"

ALLOWED_TOKENS = (
    "chrome",
    "firefox",
    "edge",
    "safari-macos",
    "safari-ios",
    "chrome-android",
    "in-app",
)
MODES = ("iframe", "iframe-except", "redirect")


@pytest.fixture
def handoff(load_client_module):
    return load_client_module("services/handoff")


class FakeFrame:
    def __init__(self):
        self.src = ""


# --- the vocabulary and classify -------------------------------------------


def test_the_closed_vocabulary_is_exactly_the_seven_tokens(handoff):
    assert tuple(handoff.BROWSER_TOKENS) == ALLOWED_TOKENS


@pytest.mark.parametrize(
    "user_agent, touch, expected",
    [
        (WINDOWS_CHROME, 0, "chrome"),
        (LINUX_HEADLESS_CHROME, 0, "chrome"),
        (WINDOWS_EDGE, 0, "edge"),
        (ANDROID_EDGE, 0, "edge"),
        (DESKTOP_FIREFOX, 0, "firefox"),
        (ANDROID_FIREFOX, 0, "firefox"),
        (MACOS_SAFARI, 0, "safari-macos"),
        (IPHONE_SAFARI, 0, "safari-ios"),
        (IPHONE_CHROME, 0, "safari-ios"),
        (IPHONE_FIREFOX, 0, "safari-ios"),
        (MACOS_SAFARI, 5, "safari-ios"),
        (MACOS_SAFARI, 0, "safari-macos"),
        (ANDROID_CHROME, 0, "chrome-android"),
        (ANDROID_WEBVIEW, 0, "in-app"),
        (FACEBOOK_IPHONE, 0, "in-app"),
        (INSTAGRAM_ANDROID, 0, "in-app"),
        (LINE_APP, 0, "in-app"),
        (WECHAT, 0, "in-app"),
        ("curl/8.0", 0, "other"),
        ("", 0, "other"),
        (None, 0, "other"),
    ],
)
def test_classify_one_user_agent_per_token(handoff, user_agent, touch, expected):
    assert handoff.classify(user_agent, touch) == expected


def test_in_app_wins_over_every_other_rule(handoff):
    assert handoff.classify(FACEBOOK_IPHONE + " Safari/604.1", 5) == "in-app"
    assert handoff.classify(WINDOWS_EDGE + " Instagram 1.0", 0) == "in-app"


@pytest.mark.parametrize("value", [5, 5.5, b"Chrome/1", [], {}, object(), True])
def test_classify_never_raises_for_a_non_string(handoff, value):
    assert handoff.classify(value) == "other"


def test_classify_never_raises_for_odd_strings(handoff):
    for text in ("\x00", "é" * 5000, "Chrome/", "Macintosh", "ANDROID"):
        assert handoff.classify(text) in ALLOWED_TOKENS + ("other",)


def test_classify_tolerates_a_bad_touch_count(handoff):
    assert handoff.classify(MACOS_SAFARI, None) == "safari-macos"


# --- parse_redirect_browsers ------------------------------------------------


def test_parse_reads_a_comma_list(handoff):
    assert handoff.parse_redirect_browsers("safari-ios, in-app") == (
        "safari-ios",
        "in-app",
    )


def test_parse_ignores_case_and_spacing(handoff):
    assert handoff.parse_redirect_browsers("  Safari-iOS ,IN-APP ") == (
        "safari-ios",
        "in-app",
    )


def test_parse_keeps_a_repeated_token_once(handoff):
    assert handoff.parse_redirect_browsers("in-app, safari-ios, in-app") == (
        "in-app",
        "safari-ios",
    )


@pytest.mark.parametrize("text", ["none", "None", "", "  ", " NONE "])
def test_parse_none_and_empty_give_an_empty_tuple(handoff, text):
    assert handoff.parse_redirect_browsers(text) == ()


def test_parse_refuses_none_mixed_with_a_token(handoff):
    with pytest.raises(ValueError):
        handoff.parse_redirect_browsers("safari-ios, none")


@pytest.mark.parametrize("word", ["safari", "iphone", "other", "ios"])
def test_parse_refuses_a_word_outside_the_vocabulary(handoff, word):
    with pytest.raises(ValueError) as caught:
        handoff.parse_redirect_browsers("in-app, " + word)
    text = str(caught.value)
    assert word in text
    for token in ALLOWED_TOKENS:
        assert token in text


# --- choose and method_for --------------------------------------------------

ALL_TOKENS = ALLOWED_TOKENS + ("other",)


@pytest.mark.parametrize("token", ALL_TOKENS)
def test_iframe_mode_embeds_for_every_token(handoff, token):
    assert handoff.choose("iframe", ("safari-ios",), token) == "iframe"


@pytest.mark.parametrize("token", ALL_TOKENS)
def test_redirect_mode_redirects_for_every_token(handoff, token):
    assert handoff.choose("redirect", (), token) == "redirect"


@pytest.mark.parametrize("token", ALL_TOKENS)
def test_iframe_except_follows_the_list_and_redirects_other(handoff, token):
    listed = ("safari-ios", "in-app")
    expected = "redirect" if token in listed or token == "other" else "iframe"
    assert handoff.choose("iframe-except", listed, token) == expected


def test_choose_truth_table_covers_three_modes_and_eight_tokens(handoff):
    listed = ("safari-ios", "in-app")
    seen = 0
    for mode in MODES:
        for token in ALL_TOKENS:
            if mode == "iframe":
                expected = "iframe"
            elif mode == "redirect":
                expected = "redirect"
            else:
                expected = (
                    "redirect" if token in listed or token == "other" else "iframe"
                )
            assert handoff.choose(mode, listed, token) == expected, (mode, token)
            seen += 1
    assert seen == 24


@pytest.mark.parametrize("mode", ["", "Iframe", "embed", None])
def test_choose_refuses_an_unknown_mode(handoff, mode):
    with pytest.raises(ValueError) as caught:
        handoff.choose(mode, (), "chrome")
    assert str(mode) in str(caught.value)


def test_method_for_reads_the_constants_at_call_time(handoff, monkeypatch):
    monkeypatch.setattr(handoff, "HANDOFF_MODE", "iframe-except")
    monkeypatch.setattr(handoff, "REDIRECT_BROWSERS", ("safari-ios",))
    assert handoff.method_for(IPHONE_SAFARI) == "redirect"
    assert handoff.method_for(WINDOWS_CHROME) == "iframe"
    assert handoff.method_for(MACOS_SAFARI, 5) == "redirect"
    monkeypatch.setattr(handoff, "HANDOFF_MODE", "redirect")
    assert handoff.method_for(WINDOWS_CHROME) == "redirect"
    monkeypatch.setattr(handoff, "HANDOFF_MODE", "iframe")
    assert handoff.method_for(IPHONE_SAFARI) == "iframe"


# --- start ------------------------------------------------------------------


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "//a.example", "", None, "data:text/html,x"]
)
def test_start_refuses_a_non_http_address_and_leaves_the_frame(handoff, url):
    frame = FakeFrame()
    with pytest.raises(ValueError):
        handoff.start(url, frame, user_agent=WINDOWS_CHROME)
    assert frame.src == ""


def test_start_sets_the_frame_source_for_the_embed(handoff, monkeypatch):
    monkeypatch.setattr(handoff, "HANDOFF_MODE", "iframe")
    monkeypatch.setattr(handoff, "REDIRECT_BROWSERS", ())
    frame = FakeFrame()
    how = handoff.start("https://vdo.example/?room=abc", frame, WINDOWS_CHROME)
    assert how == "iframe"
    assert frame.src == "https://vdo.example/?room=abc"


def test_the_listed_iphone_is_sent_to_the_redirect(handoff, monkeypatch):
    monkeypatch.setattr(handoff, "HANDOFF_MODE", "iframe-except")
    monkeypatch.setattr(handoff, "REDIRECT_BROWSERS", ("safari-ios",))
    assert handoff.method_for(IPHONE_SAFARI) == "redirect"


# --- the pinned decision --------------------------------------------------


def test_handoff_mode_equals_the_pinned_value(handoff):
    recorded = PINNED_MODE
    mode = handoff.HANDOFF_MODE
    assert mode in MODES
    assert mode == recorded


def test_redirect_browsers_equal_the_pinned_value(handoff):
    recorded = PINNED_REDIRECT_BROWSERS
    words = [] if recorded.lower() == "none" else recorded.split(",")
    words = [word.strip().lower() for word in words if word.strip()]
    outside = [word for word in words if word not in ALLOWED_TOKENS]
    assert not outside, (
        "Pinned redirect list uses words outside the closed vocabulary: stop and"
        f" ask the lead. Words: {outside}"
    )
    assert isinstance(handoff.REDIRECT_BROWSERS_TEXT, str)
    expected = handoff.parse_redirect_browsers(recorded)
    from_text = handoff.parse_redirect_browsers(handoff.REDIRECT_BROWSERS_TEXT)
    in_module = handoff.REDIRECT_BROWSERS
    assert from_text == expected
    assert in_module == expected


def test_mode_and_list_are_consistent(handoff):
    if handoff.HANDOFF_MODE == "iframe-except":
        assert handoff.REDIRECT_BROWSERS
    if handoff.HANDOFF_MODE == "iframe":
        assert not handoff.REDIRECT_BROWSERS


# --- the module text --------------------------------------------------------


def test_the_two_settings_are_on_lines_of_their_own():
    text = HANDOFF_SOURCE.read_text(encoding="utf-8")
    assert re.search(
        r'^HANDOFF_MODE = "(iframe|iframe-except|redirect)"$', text, re.MULTILINE
    )
    assert re.search(r'^REDIRECT_BROWSERS_TEXT = ".*"$', text, re.MULTILINE)


def test_the_module_stays_skulpt_safe():
    text = HANDOFF_SOURCE.read_text(encoding="utf-8")
    code = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    for banned in ("innerHTML", "import re", "typing", "contextlib"):
        assert banned not in code, banned
    module_imports = [
        line for line in code.splitlines() if line.startswith(("import ", "from "))
    ]
    assert len(module_imports) == 1
    assert "iris.services" in module_imports[0]
    assert "join" in module_imports[0]


# --- Brave ------------------------------------------------------------------
# Brave sends a plain Chrome user agent, and its Shields block third-party
# storage in the room's iframe, so the room asks for the name again. It must
# redirect, while the same user agent in real Chrome keeps the iframe.


class _Brave:
    def __init__(self, result=True, fail=False):
        self.result = result
        self.fail = fail

    def isBrave(self):
        if self.fail:
            raise RuntimeError("no")
        return self.result


class _Window:
    def __init__(self, **navigator):
        self.navigator = type("Navigator", (), navigator)()


def test_brave_redirects_where_the_same_chrome_agent_embeds(handoff):
    assert handoff.method_for(WINDOWS_CHROME) == "iframe"
    assert handoff.method_for(WINDOWS_CHROME, 0, True) == "redirect"
    assert handoff.method_for(ANDROID_CHROME, 0, True) == "redirect"


def test_detect_brave_reads_the_promise_check(handoff):
    assert handoff.detect_brave(_Window(brave=_Brave(True))) is True
    assert handoff.detect_brave(_Window(brave=_Brave(False))) is False


def test_detect_brave_falls_back_to_not_brave(handoff):
    assert handoff.detect_brave(_Window()) is False
    assert handoff.detect_brave(_Window(brave=None)) is False
    assert handoff.detect_brave(_Window(brave=_Brave(fail=True))) is False
    assert handoff.detect_brave(None) is False
