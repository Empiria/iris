# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from routing import router

from iris.services import page_language, routes  # noqa: F401  # pyright: ignore[reportAttributeAccessIssue]

page_language.apply()

router.clear_cache()
router.launch()
