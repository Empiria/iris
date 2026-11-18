# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from routing import router


class SignupRoute(router.Route):
    path = "/"
    form = "iris.SignupSpike"
