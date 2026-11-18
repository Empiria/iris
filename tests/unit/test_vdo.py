# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import ast
import urllib.parse
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

SCREEN_SHARE = "ssq=-1&sharperscreen&rbr=50000&trb=50000&crb&codec=av1,vp9,vp8,h264&q=0"


@pytest.fixture
def vdo(load_client_module):
    return load_client_module("services/vdo")


def test_vdo_py_has_no_imports():
    tree = ast.parse((ROOT / "client_code/services/vdo.py").read_text())
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert imports == []


def test_defaults(vdo):
    assert vdo.DEFAULT_ORIGIN == "https://vdo.ninja"
    assert vdo.DEFAULT_PROFILE == ""


# --- origin ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("https://Vdo.Ninja/", "https://vdo.ninja"),
        ("https://meet.tanti.org.uk", "https://meet.tanti.org.uk"),
        ("http://localhost:3030", "http://localhost:3030"),
        ("http://127.0.0.1:8080", "http://127.0.0.1:8080"),
        ("http://localhost", "http://localhost"),
        ("https://vdo.ninja:8443", "https://vdo.ninja:8443"),
    ],
)
def test_normalise_origin_accepts(vdo, given, expected):
    assert vdo.normalise_origin(given) == expected


@pytest.mark.parametrize(
    "given",
    [
        "http://vdo.ninja",
        "javascript:alert(1)",
        "https://vdo.ninja@evil.example",
        "https://vdo.ninja/path",
        "https://vdo.ninja/?x=1",
        "https://vdo.ninja#x",
        "https://vdo.ninja\\evil",
        "",
        " https://a b.example",
        "ftp://x",
        "https://",
        "https://a.example:port",
        "http://localhost:",
        "http://localhost.evil.example",
        None,
    ],
)
def test_normalise_origin_refuses(vdo, given):
    with pytest.raises(ValueError):
        vdo.normalise_origin(given)


# --- profile --------------------------------------------------------------


def test_validate_profile_empty_and_screen_share(vdo):
    assert vdo.validate_profile("") == ""
    assert vdo.validate_profile(None) == ""
    assert vdo.validate_profile(SCREEN_SHARE) == SCREEN_SHARE


def test_validate_profile_trims_separators(vdo):
    assert vdo.validate_profile("?&ssq=-1&") == "ssq=-1"


@pytest.mark.parametrize(
    "profile",
    [
        "relay",
        "privacy",
        "private",
        "icefilter",
        "tcp",
        "meshcast",
        "meshcastcode",
        "Relay",
        "RELAY=1",
        "%72elay",
        "%6Deshcast",
        "ssq=-1&relay=1",
        "relaymode",
    ],
)
def test_validate_profile_refuses_media_path_keys(vdo, profile):
    with pytest.raises(ValueError):
        vdo.validate_profile(profile)


@pytest.mark.parametrize("profile", ["turn=x", "stun=y", "nomeshcast"])
def test_validate_profile_allows_turn_stun_nomeshcast(vdo, profile):
    assert vdo.validate_profile(profile) == profile


@pytest.mark.parametrize(
    "profile",
    [
        "room=x",
        "label=x",
        "salt=x",
        "hash=x",
        "password=x",
        "r=x",
        "roomid=x",
        "l=x",
        "h=x",
        "pw=x",
        "p=x",
    ],
)
def test_validate_profile_refuses_names_iris_sets(vdo, profile):
    with pytest.raises(ValueError):
        vdo.validate_profile(profile)


@pytest.mark.parametrize("profile", ["a=b c", "a=b\nc", "a=b#c", "a=b\tc", "a=\x00"])
def test_validate_profile_refuses_unsafe_characters(vdo, profile):
    with pytest.raises(ValueError):
        vdo.validate_profile(profile)


def test_validate_profile_error_names_key_not_value(vdo):
    with pytest.raises(ValueError) as caught:
        vdo.validate_profile("relay=SECRETVALUE")
    assert "relay" in str(caught.value)
    assert "SECRETVALUE" not in str(caught.value)

    with pytest.raises(ValueError) as caught:
        vdo.validate_profile("room=SECRETVALUE")
    assert "room" in str(caught.value)
    assert "SECRETVALUE" not in str(caught.value)


def test_profile_keys(vdo):
    assert vdo.profile_keys(SCREEN_SHARE)[:3] == ["ssq", "sharperscreen", "rbr"]
    assert vdo.profile_keys("") == []


# --- quote ----------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "",
        "abc-._~",
        "a b",
        "ü",
        "日本語",
        "a&b=c#d",
        "100%",
        "".join(chr(c) for c in range(33, 73)),
        "\U0001f600 smile",
        "Ann Lee\n",
    ],
)
def test_quote_matches_urllib(vdo, text):
    assert vdo.quote(text) == urllib.parse.quote(text, safe="")


def test_unquote_decodes_ascii_only(vdo):
    assert vdo.unquote("%72elay") == "relay"
    assert vdo.unquote("%C3%BC") == "%C3%BC"
    assert vdo.unquote("100%") == "100%"
    assert vdo.unquote("%zz") == "%zz"
    # Decoded to a fixpoint, so double encoding does not hide a key.
    assert vdo.unquote("%2572elay") == "relay"


def test_validate_profile_refuses_double_encoded_key(vdo):
    with pytest.raises(ValueError):
        vdo.validate_profile("%2572elay")
    with pytest.raises(ValueError):
        vdo.validate_profile("room%3Dx")


# --- build_join_url -------------------------------------------------------


def test_build_join_url_query_form(vdo):
    url = vdo.build_join_url("https://vdo.ninja/", "room1234", SCREEN_SHARE, "Ann Lee")

    assert url == f"https://vdo.ninja/?room=room1234&label=Ann%20Lee&{SCREEN_SHARE}"


def test_build_join_url_adds_salt_only_when_set(vdo):
    url = vdo.build_join_url("https://vdo.ninja", "r1", SCREEN_SHARE, "A", salt="s")

    assert url.endswith("&salt=s")
    assert "salt" not in vdo.build_join_url("https://vdo.ninja", "r1", "", "A")


def test_build_join_url_fragment_form(vdo):
    url = vdo.build_join_url(
        "https://vdo.ninja/", "room1234", SCREEN_SHARE, "Ann Lee", in_fragment=True
    )

    assert url == f"https://vdo.ninja/?{SCREEN_SHARE}#room=room1234&label=Ann%20Lee"


def test_build_join_url_fragment_with_empty_profile_has_no_query(vdo):
    url = vdo.build_join_url("https://vdo.ninja", "r1", "", "A", in_fragment=True)

    assert url == "https://vdo.ninja/#room=r1&label=A"


def test_build_join_url_empty_profile_query_form(vdo):
    assert (
        vdo.build_join_url("https://vdo.ninja", "r1", "", "A")
        == "https://vdo.ninja/?room=r1&label=A"
    )


def test_build_join_url_fragment_carries_salt(vdo):
    url = vdo.build_join_url(
        "https://vdo.ninja", "r1", "", "A", salt="s", in_fragment=True
    )

    assert url == "https://vdo.ninja/#room=r1&label=A&salt=s"


PASSWORD = "0123456789abcdef01234567"


def test_build_join_url_fragment_carries_the_password_after_the_label(vdo):
    url = vdo.build_join_url(
        "https://vdo.ninja",
        "r1",
        SCREEN_SHARE,
        "A",
        salt="s",
        password=PASSWORD,
        in_fragment=True,
    )

    assert url == (
        f"https://vdo.ninja/?{SCREEN_SHARE}#room=r1&label=A&password={PASSWORD}&salt=s"
    )


def test_build_join_url_password_never_goes_in_the_query(vdo):
    query_part = vdo.build_join_url(
        "https://vdo.ninja", "r1", "", "A", password=PASSWORD, in_fragment=True
    ).split("#")[0]

    assert PASSWORD not in query_part
    with pytest.raises(ValueError) as refused:
        vdo.build_join_url(
            "https://vdo.ninja", "r1", "", "A", password=PASSWORD, in_fragment=False
        )
    assert PASSWORD not in str(refused.value)


def test_build_join_url_without_a_password_is_unchanged(vdo):
    for in_fragment in (False, True):
        assert vdo.build_join_url(
            "https://vdo.ninja",
            "r1",
            SCREEN_SHARE,
            "A",
            salt="s",
            in_fragment=in_fragment,
        ) == vdo.build_join_url(
            "https://vdo.ninja",
            "r1",
            SCREEN_SHARE,
            "A",
            salt="s",
            password=None,
            in_fragment=in_fragment,
        )
    assert "password" not in vdo.build_join_url("https://vdo.ninja", "r1", "", "A")


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "a" * 50,
        "has space",
        "a&b",
        "a#b",
        "a=b",
        "pass%20",
        "naïve",
        "名前",
        5,
        b"abc",
    ],
    ids=[
        "empty",
        "too-long",
        "space",
        "amp",
        "hash",
        "equals",
        "percent",
        "accent",
        "cjk",
        "int",
        "bytes",
    ],
)
def test_build_join_url_refuses_a_bad_password(vdo, bad):
    with pytest.raises(ValueError):
        vdo.build_join_url(
            "https://vdo.ninja", "r1", "", "A", password=bad, in_fragment=True
        )


@pytest.mark.parametrize("good", ["a", "A1", "a" * 49, "Z9z0"])
def test_build_join_url_accepts_one_to_forty_nine_alphanumerics(vdo, good):
    url = vdo.build_join_url(
        "https://vdo.ninja", "r1", "", "A", password=good, in_fragment=True
    )

    assert "&password=" + good in url


@pytest.mark.parametrize("in_fragment", [False, True])
def test_build_join_url_never_emits_meshcast_or_relay(vdo, in_fragment):
    url = vdo.build_join_url(
        "https://vdo.ninja", "r1", SCREEN_SHARE, "A", in_fragment=in_fragment
    )

    assert "meshcast" not in url
    assert "relay" not in url


def test_build_join_url_quotes_the_label(vdo):
    url = vdo.build_join_url("https://vdo.ninja", "r1", "", "a&room=x#y")

    assert "label=a%26room%3Dx%23y" in url


@pytest.mark.parametrize(
    ("origin", "room", "profile"),
    [
        ("https://vdo.ninja", "", ""),
        ("http://vdo.ninja", "r1", ""),
        ("https://vdo.ninja/x", "r1", ""),
        ("https://vdo.ninja", "r1", "relay"),
        ("https://vdo.ninja", "r1", "meshcast"),
        ("https://vdo.ninja", "r1", "room=other"),
    ],
)
def test_build_join_url_revalidates_what_it_is_given(vdo, origin, room, profile):
    with pytest.raises(ValueError):
        vdo.build_join_url(origin, room, profile, "A")
