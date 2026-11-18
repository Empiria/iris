# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import anvil.server
from routing import router


class StaffRoute(router.Route):
    path = "/staff"
    form = "iris.StaffSpike"


class HomeRoute(router.Route):
    path = "/"
    form = "iris.HelloWorld"

    def meta(self, **kwargs):
        return {"title": "Iris"}


class SlugRoute(router.Route):
    """Declared after /staff and /: fixed paths first, the catch-all last."""

    path = "/:slug"
    form = "iris.SlugSpike"
    not_found_form = "iris.SlugSpike"

    def load_data(self, **loader_args):
        slug = loader_args["params"]["slug"]
        found = anvil.server.call("lookup", slug)
        if found is None:
            raise router.NotFound()
        return found

    def meta(self, **kwargs):
        return {"title": "Slug spike"}
