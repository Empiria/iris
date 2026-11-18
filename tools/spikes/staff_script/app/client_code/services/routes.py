# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from routing import router


class ScriptRoute(router.Route):
    path = "/"
    form = "iris.ScriptSpike"
