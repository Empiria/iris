"""Passphrase generation and normalisation for permanent rooms.

Loads on both sides (Skulpt in the browser, CPython on the server). Generation
only runs on the server, through `slugs.random_string`, which loads `secrets`
inside the function. There is no hashing here: the verifier is server-side.

The test vector in tests/unit/test_passphrase.py is the contract between
creating a room and joining it. Both call `normalise`, so a passphrase typed
with different case, dashes or spaces reduces to the same string. Change the
vector only on purpose, and re-check every stored verifier when you do.
"""

from iris.services import slugs  # pyright: ignore[reportAttributeAccessIssue]

PASSPHRASE_LENGTH = 12
GROUP = 4
# Longest raw input `normalise` accepts. It bounds the work a hostile caller can
# hand the server's key derivation.
MAX_INPUT = 200


def generate():
    """A fresh passphrase: 12 characters shown as xxxx-xxxx-xxxx."""
    raw = slugs.random_string(slugs.ONE_OFF_ALPHABET, PASSPHRASE_LENGTH)
    groups = [raw[i : i + GROUP] for i in range(0, len(raw), GROUP)]
    return "-".join(groups)


def normalise(text):
    """Lower-case `text` and drop spaces and dashes, or raise ValueError.

    It does not judge strength or alphabet: a passphrase typed wrongly just
    won't match the verifier.
    """
    if not isinstance(text, str):
        raise ValueError("Enter the passphrase.")
    if len(text) > MAX_INPUT:
        raise ValueError("That passphrase is too long.")
    kept = [ch for ch in text.lower() if ch != "-" and not ch.isspace()]
    if not kept:
        raise ValueError("Enter the passphrase.")
    return "".join(kept)
