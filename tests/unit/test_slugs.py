import pytest


@pytest.fixture
def slugs(load_client_module):
    return load_client_module("services/slugs")


def test_normalise_lowers_and_strips(slugs):
    assert slugs.normalise(" AbC2 ") == "abc2"
    assert slugs.normalise(None) == ""


@pytest.mark.parametrize("slug", ["dk2wjd9d", "infinite-worlds", "abc"])
def test_looks_like_slug_accepts(slugs, slug):
    assert slugs.looks_like_slug(slug)


@pytest.mark.parametrize(
    "slug",
    ["", "ab", "a" * 65, "Has Space", "../x", "-lead", "trail-", "a_b", None],
)
def test_looks_like_slug_refuses(slugs, slug):
    assert not slugs.looks_like_slug(slug)


def test_reserved_slugs_are_refused(slugs):
    assert "admin" in slugs.RESERVED_SLUGS
    for slug in slugs.RESERVED_SLUGS:
        assert not slugs.looks_like_slug(slug), slug


def test_one_off_slug_shape_and_alphabet(slugs):
    seen = set()
    for _ in range(2000):
        slug = slugs.new_one_off_slug()
        assert len(slug) == 8
        assert set(slug) <= set(slugs.ONE_OFF_ALPHABET)
        assert not set(slug) & set("ilo01")
        seen.add(slug)
    assert len(seen) > 1
    assert len(slugs.ONE_OFF_ALPHABET) == 31


def test_vdo_room_shape_and_independence(slugs):
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789")
    for _ in range(2000):
        slug = slugs.new_one_off_slug()
        room = slugs.new_vdo_room()
        assert len(room) == 20
        assert set(room) <= allowed
        assert room != slug


def test_random_string_uses_secrets_not_random(slugs, monkeypatch):
    import secrets

    calls = []

    def fake_choice(alphabet):
        calls.append(alphabet)
        return alphabet[0]

    monkeypatch.setattr(secrets, "choice", fake_choice)

    assert slugs.random_string("xyz", 4) == "xxxx"
    assert len(calls) == 4


@pytest.mark.parametrize(
    "typed, expected",
    [
        ("  Acme Board  ", "acme-board"),
        ("acme__board", "acme-board"),
        ("a  b", "a-b"),
        ("Acme_ Board", "acme-board"),
        ("infinite-worlds", "infinite-worlds"),
        ("ABC", "abc"),
    ],
)
def test_clean_room_slug_makes_a_readable_slug(slugs, typed, expected):
    cleaned = slugs.clean_room_slug(typed)
    assert cleaned == expected
    assert slugs.looks_like_slug(cleaned)


@pytest.mark.parametrize(
    "typed, message",
    [
        ("", "at least 3 characters"),
        ("   ", "at least 3 characters"),
        ("ab", "at least 3 characters"),
        (None, "at least 3 characters"),
        ("a" * 65, "at most 64"),
        ("acme!", "letters, numbers and dashes"),
        ("acme/board", "letters, numbers and dashes"),
        ("-acme", "start or end with a dash"),
        ("acme-", "start or end with a dash"),
        ("acme_", "start or end with a dash"),
        ("admin", "That name is reserved."),
        ("Admin", "That name is reserved."),
    ],
)
def test_clean_room_slug_refuses_with_an_actionable_message(slugs, typed, message):
    with pytest.raises(ValueError) as excinfo:
        slugs.clean_room_slug(typed)
    assert message in str(excinfo.value)


def test_clean_room_slug_accepts_the_length_limits(slugs):
    assert slugs.clean_room_slug("abc") == "abc"
    assert slugs.clean_room_slug("a" * 64) == "a" * 64
