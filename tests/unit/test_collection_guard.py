"""The guard in tests/conftest.py, pinned with real pytest subprocesses.

A collection hook cannot be tested honestly in-process, so these only collect.
They need no stack, no browser and no network.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def collect(*args):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "--collect-only",
            "-q",
            *args,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize("args", [("tests/unit", "tests/e2e"), ("tests",)])
def test_mixed_collection_exits_4(args):
    result = collect(*args)

    assert result.returncode == 4
    assert "Run `just unit` and `just e2e` separately" in result.stdout + result.stderr


def test_unit_suite_alone_is_allowed():
    result = collect("tests/unit")

    assert result.returncode == 0
