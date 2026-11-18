"""Point Playwright at the repo's browser cache, as the justfile does.

`just setup` installs chromium into the git-ignored `.anvil/ms-playwright`, so a
bare `uv run pytest tests/e2e` finds the same browser whatever HOME is. An
explicit PLAYWRIGHT_BROWSERS_PATH still wins.
"""

import os
from pathlib import Path

BROWSERS = Path(__file__).resolve().parents[2] / ".anvil" / "ms-playwright"

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS))
