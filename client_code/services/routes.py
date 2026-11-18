import anvil.server
from routing import router

from iris.services import join  # pyright: ignore[reportAttributeAccessIssue]

# Routes match in the order they are declared, so / and /staff come before the
# /:slug catch-all (spike S1c). Reserved slugs such as "staff" are refused again
# by join.is_joinable_slug, so a meeting can never shadow a page.


class StaffRoute(router.Route):
    path = "/"
    form = "iris.Staff"

    def meta(self, **kwargs):
        return {"title": "Iris staff"}


class StaffAliasRoute(StaffRoute):
    # /staff keeps working for existing bookmarks. It is a separate route class
    # because a Route has one path.
    path = "/staff"


class JoinRoute(router.Route):
    path = "/:slug"
    form = "iris.Join"

    def load_data(self, **loader_args):
        # Returns a state dict, never raises and never returns None, so the form
        # decides what to show and no error banner appears (spike S1b).
        return join.load_meeting(loader_args["params"]["slug"], anvil.server.call)

    def meta(self, **kwargs):
        return {"title": "Join meeting"}
