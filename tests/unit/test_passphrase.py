"""Passphrase generation and normalisation.

NORMALISE_VECTOR is the contract between creating a room and joining it: both
call `passphrase.normalise`, and a typed passphrase must reduce to the same
string the verifier was built from. Change a row here only on purpose, and
re-check every stored verifier.
"""

import re

import pytest


@pytest.fixture
def passphrase(load_client_module):
    return load_client_module("services/passphrase.py")


@pytest.fixture
def slugs(load_client_module):
    return load_client_module("services/slugs")


NORMALISE_VECTOR = [
    ("abcd-efgh-jkmn", "abcdefghjkmn"),
    ("ABCD EFGH JKMN", "abcdefghjkmn"),
    ("  abcd-efgh-jkmn\n", "abcdefghjkmn"),
    ("abcd--efgh  jkmn", "abcdefghjkmn"),
    ("AbCd efgh-JKMN", "abcdefghjkmn"),
    ("Ab1-x", "ab1x"),
]


@pytest.mark.parametrize("typed, expected", NORMALISE_VECTOR)
def test_normalise_vector(passphrase, typed, expected):
    assert passphrase.normalise(typed) == expected


def test_mixed_case_and_dashes_normalise_the_same(passphrase):
    assert passphrase.normalise("AbCd efgh-JKMN") == passphrase.normalise(
        "abcd-efgh-jkmn"
    )


def test_generate_shape(passphrase, slugs):
    pattern = re.compile("^[%s]{4}-[%s]{4}-[%s]{4}$" % ((slugs.ONE_OFF_ALPHABET,) * 3))
    for _ in range(50):
        assert pattern.match(passphrase.generate())


def test_generate_is_random(passphrase):
    assert len({passphrase.generate() for _ in range(200)}) == 200


def test_generated_passphrase_normalises_to_twelve_characters(passphrase):
    assert passphrase.PASSPHRASE_LENGTH == 12
    value = passphrase.generate()
    assert len(passphrase.normalise(value)) == 12
    assert passphrase.normalise(value) == value.replace("-", "")


def test_generate_reuses_the_slug_random_source(passphrase, slugs, monkeypatch):
    calls = []

    def fake_random_string(alphabet, length):
        calls.append((alphabet, length))
        return "q" * length

    monkeypatch.setattr(slugs, "random_string", fake_random_string)
    assert passphrase.generate() == "qqqq-qqqq-qqqq"
    assert calls == [(slugs.ONE_OFF_ALPHABET, 12)]


@pytest.mark.parametrize("empty", ["", " - ", "   ", "---", "\n"])
def test_normalise_refuses_an_empty_result(passphrase, empty):
    with pytest.raises(ValueError) as excinfo:
        passphrase.normalise(empty)
    assert str(excinfo.value) == "Enter the passphrase."


@pytest.mark.parametrize("bad", [None, 12345, b"abcd", ["abcd"]])
def test_normalise_refuses_a_non_string(passphrase, bad):
    with pytest.raises(ValueError):
        passphrase.normalise(bad)


def test_normalise_bounds_the_input(passphrase):
    assert passphrase.normalise("a" * 200) == "a" * 200
    with pytest.raises(ValueError):
        passphrase.normalise("a" * 201)


def test_module_holds_no_hashing_or_top_level_secrets():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2] / "client_code/services/passphrase.py"
    ).read_text()
    assert "hashlib" not in source
    assert not re.search(r"^(import secrets|from secrets)", source, re.M)
