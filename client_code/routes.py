# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Top-level import of the route classes.

Keep this module. Without it a cold load of /admin or /<slug> answers
"No matching API endpoint" (the e2e suite fails on a cold /admin); with it the
app serves those paths. The real routes live in `iris.services.routes`.
"""

from iris.services import routes  # noqa: F401  # pyright: ignore[reportAttributeAccessIssue]
