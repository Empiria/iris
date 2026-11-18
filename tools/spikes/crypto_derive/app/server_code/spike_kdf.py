# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import hashlib
import time

import anvil.server

ITERATIONS = (100_000, 300_000, 600_000)
SALT = b"iris:spike"
PASSPHRASE = b"spike-pass-1234"


@anvil.server.callable
def spike_kdf_timing():
    """S3: milliseconds one hashlib.pbkdf2_hmac call takes on this server.

    Spike-only: it takes no input, returns no data and is never in the product.
    Each count is timed three times and the median is returned, so one slow
    scheduling slice does not stand for the cost.
    """
    timings = {}
    for iterations in ITERATIONS:
        runs = []
        for _ in range(3):
            start = time.perf_counter()
            hashlib.pbkdf2_hmac("sha256", PASSPHRASE, SALT, iterations, 32)
            runs.append((time.perf_counter() - start) * 1000.0)
        runs.sort()
        timings[str(iterations)] = round(runs[1], 1)
    return timings
