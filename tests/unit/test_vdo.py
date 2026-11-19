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


PRODUCTION = (
    "sharperscreen=true&rbr=50000&codec=av1,vp9,vp8,h264&crb=true&q=0&ssq=-1"
    "&trb=50000&proaudio"
)


def test_validate_profile_accepts_the_production_profile(vdo):
    assert vdo.validate_profile(PRODUCTION) == PRODUCTION
    assert vdo.validate_profile("proaudio=true&sharperscreen") == (
        "proaudio=true&sharperscreen"
    )


@pytest.mark.parametrize(
    "profile",
    ["turn=x", "stun=y", "wss=x", "proxy=1", "push=x", "pass=x", "pwd=x", "dir=x"],
)
def test_validate_profile_refuses_signalling_and_ice_overrides(vdo, profile):
    with pytest.raises(ValueError) as caught:
        vdo.validate_profile(profile)
    assert "is not allowed" in str(caught.value)


@pytest.mark.parametrize("profile", ["nomeshcast", "bogus=1", "Bogus", "ssq=-1&zzz"])
def test_validate_profile_refuses_unknown_keys(vdo, profile):
    with pytest.raises(ValueError) as caught:
        vdo.validate_profile(profile)
    assert "not on the allowed list" in str(caught.value)


def test_validate_profile_refuses_duplicate_keys(vdo):
    with pytest.raises(ValueError) as caught:
        vdo.validate_profile("q=0&Q=1")
    assert "'q' appears more than once" in str(caught.value)
    with pytest.raises(ValueError):
        vdo.validate_profile("proaudio&proaudio=true")


def test_validate_profile_extra_keys_extend_the_allowlist(vdo):
    assert vdo.validate_profile("bogus=1", ["bogus"]) == "bogus=1"
    assert vdo.parse_extra_keys(" Bogus, other ,,") == ["bogus", "other"]
    # Extra keys never lift a refusal.
    for bad in ("relay", "turn=x", "room=x"):
        with pytest.raises(ValueError):
            vdo.validate_profile(bad, [bad.split("=")[0]])


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


# --- per-visit overrides ---------------------------------------------------


def test_override_replaces_the_profiles_key_in_place_of_repeating_it(vdo):
    merged = vdo.merge_profile("q=0&rbr=50000&crb", "q=2")

    assert merged == "rbr=50000&crb&q=2"
    assert vdo.validate_profile(merged, check_allowed=False) == merged


def test_override_replaces_the_other_spelling_of_the_same_setting(vdo):
    merged = vdo.merge_profile("quality=0&rbr=1", "q=2&roombitrate=200")

    assert merged == "q=2&roombitrate=200"


def test_merge_with_no_overrides_is_the_profile(vdo):
    assert vdo.merge_profile("q=0&crb", "") == "q=0&crb"
    assert vdo.merge_profile("", "q=2") == "q=2"


def test_merge_refuses_a_key_that_is_not_allowed(vdo):
    for bad in ("password=x", "room=x", "salt=x", "turn=x", "meshcast", "nosuchkey"):
        with pytest.raises(ValueError):
            vdo.merge_profile("q=0", bad)


def test_parse_keeps_allowed_keys_and_lists_the_rest(vdo):
    overrides, ignored = vdo.parse_overrides(
        "?q=2&rbr=200&password=x&room=y&salt=s&label=l&wss=evil&turn=t&foo=1&noscale"
    )

    assert overrides == "q=2&rbr=200&noscale"
    assert ignored == ["password", "room", "salt", "label", "wss", "turn", "foo"]


def test_parse_decodes_the_key_before_checking_it(vdo):
    overrides, ignored = vdo.parse_overrides("%70assword=x&%2571ualit%79=1&relay%3D1")

    # An encoded allowed key is accepted under its decoded name; encoded denied
    # keys are still refused.
    assert overrides == "quality=1"
    assert ignored == ["password", "relay"]


def test_parse_ignores_a_value_with_a_character_outside_the_safe_set(vdo):
    overrides, ignored = vdo.parse_overrides(
        "q=2%26room%3Dx&rbr=1%23&fps=<b>&codec=h264,vp8"
    )

    assert overrides == "codec=h264,vp8"
    assert ignored == ["q", "rbr", "fps"]


def test_parse_keeps_the_first_of_a_repeated_setting(vdo):
    overrides, ignored = vdo.parse_overrides("q=2&quality=1&q=0")

    assert overrides == "q=2"
    assert ignored == ["quality", "q"]


def test_parse_of_nothing(vdo):
    assert vdo.parse_overrides("") == ("", [])
    assert vdo.parse_overrides(None) == ("", [])
    assert vdo.parse_overrides("?") == ("", [])


def test_parse_output_always_passes_the_allowlist(vdo):
    overrides, _ = vdo.parse_overrides("ltb=300&maxbandwidth=50&tb=200&vb=500")

    assert overrides == "ltb=300&tb=200&vb=500"
    assert vdo.validate_profile(overrides) == overrides


def test_the_notice_is_empty_or_names_a_capped_list(vdo):
    assert vdo.override_notice([]) == ""
    text = vdo.override_notice(["a" * 100] + [f"b{i}" for i in range(9)])
    assert "a" * 24 in text and "a" * 25 not in text
    assert text.endswith("and 5 more.")
