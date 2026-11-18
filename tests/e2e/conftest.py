"""Point Playwright at the repo's browser cache, and provide the dev accounts.

`just setup` installs chromium into the git-ignored `.anvil/ms-playwright`, so a
bare `uv run pytest tests/e2e` finds the same browser whatever HOME is. An
explicit PLAYWRIGHT_BROWSERS_PATH still wins.

`staff_login` and `non_staff_login` return `(email, password)` for the two local
dev accounts. The first runs `tools/create_staff.py --dev`, which makes both and
is safe to run again, so a second run in the same database passes.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BROWSERS = ROOT / ".anvil" / "ms-playwright"
LAUNCHER = ROOT / "tools" / "create_staff.py"

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS))


def _launcher_constants():
    """Load the launcher by path to read its DEV_* constants (no anvil import)."""
    spec = importlib.util.spec_from_file_location("iris_create_staff", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def staff_login():
    dev = _launcher_constants()
    result = subprocess.run(
        [sys.executable, str(LAUNCHER), "--dev"],
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"create_staff --dev failed:\n{result.stderr}")
    return dev.DEV_STAFF_EMAIL, dev.DEV_STAFF_PASSWORD


@pytest.fixture(scope="session")
def non_staff_login(staff_login):
    dev = _launcher_constants()
    return dev.DEV_VIEWER_EMAIL, dev.DEV_VIEWER_PASSWORD
