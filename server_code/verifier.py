# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Slow hash and constant-time check of a normalised room passphrase.

Server-side only, and it imports no Anvil module, so a tool can load it by path.
A stored record holds the PBKDF2-SHA256 output, its random salt and the
iteration count it was made with. The count is read back from the record, so
`ITERATIONS` can rise later without breaking rooms made earlier. The passphrase
is never stored, logged or put in an exception here.
"""

import hashlib
import hmac
import secrets

# 600000 costs about 0.1 s of server CPU per check (measured in a sandbox).
ITERATIONS = 600000
SALT_BYTES = 16


def _derive(normalised, salt, iterations):
    return hashlib.pbkdf2_hmac("sha256", normalised.encode("utf-8"), salt, iterations)


def hash_passphrase(normalised):
    """The record to store for `normalised`: verifier, verifier_salt, kdf_iterations."""
    salt = secrets.token_bytes(SALT_BYTES)
    return {
        "verifier": _derive(normalised, salt, ITERATIONS).hex(),
        "verifier_salt": salt.hex(),
        "kdf_iterations": ITERATIONS,
    }


def check_passphrase(normalised, record):
    """True when `normalised` matches the stored `record`; False otherwise.

    A missing, partial or malformed record is a plain False, so a damaged row
    refuses every attempt and raises nothing that could carry the input.
    """
    if not isinstance(normalised, str) or not isinstance(record, dict):
        return False
    try:
        stored = bytes.fromhex(record.get("verifier") or "")
        salt = bytes.fromhex(record.get("verifier_salt") or "")
        iterations = int(record.get("kdf_iterations") or 0)
    except (TypeError, ValueError):
        return False
    if not stored or not salt or iterations < 1:
        return False
    return hmac.compare_digest(_derive(normalised, salt, iterations), stored)
