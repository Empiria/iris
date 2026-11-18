# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from iris.globals import session
from iris.services import page_language, routes  # noqa: F401  # pyright: ignore[reportAttributeAccessIssue]

page_language.apply()

session.launch()
