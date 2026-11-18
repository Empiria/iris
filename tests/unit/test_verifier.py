"""server_code/verifier.py: slow hash and constant-time check of a passphrase."""

import ast
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "server_code" / "verifier.py"
# Computed once with hashlib.pbkdf2_hmac("sha256", b"abcdefghjkmn", bytes(16), 1000).
PINNED_HEX = "8e79940bea9bdc75213ce99e70fd71edcfe5fd47487c5a40ddc0443201541023"


@pytest.fixture
def verifier(load_server_module):
    return load_server_module("verifier")


def test_iterations_is_the_chosen_600000(verifier):
    assert verifier.ITERATIONS == 600000


def test_hash_returns_the_three_fields(verifier, monkeypatch):
    monkeypatch.setattr(verifier, "ITERATIONS", 1000)

    record = verifier.hash_passphrase("abcdefghjkmn")

    assert set(record) == {"verifier", "verifier_salt", "kdf_iterations"}
    assert record["kdf_iterations"] == 1000
    assert len(bytes.fromhex(record["verifier_salt"])) == 16
    assert len(bytes.fromhex(record["verifier"])) == 32


def test_hash_matches_hashlib_with_its_own_salt(verifier, monkeypatch):
    monkeypatch.setattr(verifier, "ITERATIONS", 1000)

    record = verifier.hash_passphrase("abcdefghjkmn")

    expected = hashlib.pbkdf2_hmac(
        "sha256", b"abcdefghjkmn", bytes.fromhex(record["verifier_salt"]), 1000
    )
    assert record["verifier"] == expected.hex()


def test_two_hashes_of_one_input_differ(verifier, monkeypatch):
    monkeypatch.setattr(verifier, "ITERATIONS", 1000)

    first = verifier.hash_passphrase("abcdefghjkmn")
    second = verifier.hash_passphrase("abcdefghjkmn")

    assert first["verifier_salt"] != second["verifier_salt"]
    assert first["verifier"] != second["verifier"]


def test_check_accepts_the_match_and_rejects_others(verifier, monkeypatch):
    monkeypatch.setattr(verifier, "ITERATIONS", 1000)
    record = verifier.hash_passphrase("abcdefghjkmn")

    assert verifier.check_passphrase("abcdefghjkmn", record) is True
    assert verifier.check_passphrase("abcdefghjkmm", record) is False
    assert verifier.check_passphrase("", record) is False


def test_pinned_vector_is_checked_with_the_stored_count(verifier):
    assert (
        hashlib.pbkdf2_hmac("sha256", b"abcdefghjkmn", bytes(16), 1000).hex()
        == PINNED_HEX
    )
    record = {
        "verifier": PINNED_HEX,
        "verifier_salt": "00" * 16,
        "kdf_iterations": 1000,
    }

    assert verifier.check_passphrase("abcdefghjkmn", record) is True
    assert verifier.check_passphrase("abcdefghjkmx", record) is False


def test_the_stored_count_is_honoured_not_the_constant(verifier):
    record = {
        "verifier": PINNED_HEX,
        "verifier_salt": "00" * 16,
        "kdf_iterations": 1000,
    }

    assert verifier.ITERATIONS != 1000
    assert verifier.check_passphrase("abcdefghjkmn", record) is True


@pytest.mark.parametrize(
    "record",
    [
        None,
        {},
        {"verifier": None, "verifier_salt": None, "kdf_iterations": None},
        {"verifier": "zz", "verifier_salt": "00" * 16, "kdf_iterations": 1000},
        {"verifier": PINNED_HEX, "verifier_salt": "nothex", "kdf_iterations": 1000},
        {"verifier": PINNED_HEX, "verifier_salt": "00" * 16, "kdf_iterations": 0},
    ],
    ids=["none", "empty", "nulls", "bad-verifier", "bad-salt", "zero-count"],
)
def test_an_unusable_record_is_a_plain_false(verifier, record):
    assert verifier.check_passphrase("abcdefghjkmn", record) is False


def test_a_non_string_passphrase_is_false(verifier):
    record = {
        "verifier": PINNED_HEX,
        "verifier_salt": "00" * 16,
        "kdf_iterations": 1000,
    }

    assert verifier.check_passphrase(None, record) is False
    assert verifier.check_passphrase(5, record) is False


def test_the_check_uses_a_constant_time_compare():
    assert "hmac.compare_digest" in SOURCE.read_text()


def test_it_imports_only_hashlib_hmac_and_secrets():
    tree = ast.parse(SOURCE.read_text())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add((node.module or "").split(".")[0])

    assert modules <= {"hashlib", "hmac", "secrets"}
