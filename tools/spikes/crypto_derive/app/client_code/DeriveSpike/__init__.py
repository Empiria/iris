# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import anvil.js
import anvil.server
from anvil.js.window import TextEncoder, crypto, performance

from ._anvil_designer import DeriveSpikeTemplate

PASSPHRASE = "spike-pass-1234"
SALT = "iris:spike"
FIXED_ITERATIONS = 1000
TIMED_ITERATIONS = (100000, 600000)


def _hex(buffer):
    # A Uint8Array view comes back to Python as bytes.
    view = anvil.js.window.Uint8Array(buffer)
    return "".join([format(b, "02x") for b in bytes(view)])


def derive_anvil_js(passphrase, salt, iterations):
    """S1a: SubtleCrypto from Python, with no .then() anywhere."""
    encoder = TextEncoder()
    subtle = crypto.subtle
    key = subtle.importKey(
        "raw", encoder.encode(passphrase), "PBKDF2", False, ["deriveBits"]
    )
    bits = subtle.deriveBits(
        {
            "name": "PBKDF2",
            "hash": "SHA-256",
            "salt": encoder.encode(salt),
            "iterations": iterations,
        },
        key,
        256,
    )
    return _hex(bits)


def _outcome(call):
    """('ok', value) or ('err', one-word message)."""
    try:
        return "ok", call()
    except Exception as exc:
        message = (type(exc).__name__ + ":" + str(exc)).replace(" ", "_")
        return "err", message[:160]


def _timed(call):
    start = performance.now()
    call()
    return int(round(performance.now() - start))


def _timing_parts(call):
    """One 'ms<iterations>=<ms>' (or 'error<iterations>=...') token per count."""
    parts = []
    for iterations in TIMED_ITERATIONS:
        status, value = _outcome(lambda: _timed(lambda: call(iterations)))
        label = "ms" if status == "ok" else "error"
        parts.append(label + str(iterations) + "=" + str(value))
    return parts


def _token(name, status, value):
    return name + ("=" if status == "ok" else "_error=") + str(value)


class DeriveSpike(DeriveSpikeTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)

    def _show(self, parts):
        self.dom_nodes["out"].textContent = " ".join(parts) + " DONE"

    def _call_js(self, passphrase, salt, iterations):
        return self.call_js("irisDerive", passphrase, salt, iterations)

    def _window(self, passphrase, salt, iterations):
        return anvil.js.window.irisDerive(passphrase, salt, iterations)

    def _s1a_click(self, event):
        status, value = _outcome(
            lambda: derive_anvil_js(PASSPHRASE, SALT, FIXED_ITERATIONS)
        )
        parts = ["S1a", _token("hex", status, value)]
        parts += _timing_parts(lambda n: derive_anvil_js(PASSPHRASE, SALT, n))
        self._show(parts)

    def _s1b_click(self, event):
        parts = ["S1b"]
        winner = None
        for name, call in (("call_js", self._call_js), ("window", self._window)):
            status, value = _outcome(lambda: call(PASSPHRASE, SALT, FIXED_ITERATIONS))
            parts.append(name + "=" + ("ok" if status == "ok" else "err:" + value))
            if status == "ok" and winner is None:
                winner = (name, call, value)
        if winner:
            parts += ["hex=" + str(winner[2]), "via=" + winner[0]]
            parts += _timing_parts(lambda n: winner[1](PASSPHRASE, SALT, n))
        self._show(parts)

    def _s1c_click(self, event):
        status, value = _outcome(
            lambda: derive_anvil_js(PASSPHRASE, SALT, FIXED_ITERATIONS)
        )
        parts = ["S1c", _token("anvil_js", status, value)]
        status, value = _outcome(
            lambda: self._call_js(PASSPHRASE, SALT, FIXED_ITERATIONS)
        )
        parts.append(_token("call_js", status, value))
        self._show(parts)

    def _s3_click(self, event):
        status, value = _outcome(lambda: anvil.server.call("spike_kdf_timing"))
        parts = ["S3"]
        if status == "ok":
            parts += ["ms" + k + "=" + str(value[k]) for k in sorted(value, key=int)]
        else:
            parts.append("error=" + value)
        self._show(parts)
