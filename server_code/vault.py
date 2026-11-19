# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Seals a permanent room's passphrase so an admin can read it again (D-19).

The passphrase is encrypted with Anvil's own secret encryption: an encryption
key held in the Secrets service, named by `KEY_NAME`. Only the ciphertext is
stored on the room row. The slow verifier stays as the thing guests are checked
against.

Server only, and nothing here is a callable. `unseal` returns a plain
passphrase, so it is reached only from a model method that has already
required an admin, and never from anything an anonymous caller can run.
"""

import anvil.secrets

# The Secrets service encryption key's name. Empiria's value lives in the
# app's Secrets; a fork creates its own key under this name (README).
KEY_NAME = "iris_passphrase_key"


class VaultError(ValueError):
    """The passphrase could not be sealed or unsealed.

    A ValueError, because the message is written for an admin and the client
    shows a ValueError's message. It carries no key, ciphertext or passphrase.
    """


def seal(passphrase_text):
    """The ciphertext of `passphrase_text`, ready for the room row.

    Raises VaultError when the encryption key is missing or unusable.
    """
    try:
        return anvil.secrets.encrypt_with_key(KEY_NAME, passphrase_text)
    except Exception as error:
        raise VaultError(
            "The passphrase could not be stored: the encryption key "
            + KEY_NAME
            + " is missing or unusable."
        ) from error


def unseal(ciphertext):
    """The passphrase held in `ciphertext`.

    Raises VaultError when the key is missing, or the ciphertext does not
    decrypt with it (a changed key or damaged data).
    """
    try:
        return anvil.secrets.decrypt_with_key(KEY_NAME, ciphertext)
    except Exception as error:
        raise VaultError(
            "The passphrase could not be read: the encryption key "
            + KEY_NAME
            + " is missing, or it is not the key that stored it."
        ) from error
