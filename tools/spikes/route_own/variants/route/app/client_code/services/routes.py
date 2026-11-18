from routing import router


class SlugRoute(router.Route):
    """A pathed Route with no load_data. The server route is spike_routes.py's."""

    path = "/:slug"
    form = "iris.SlugSpike"
    not_found_form = "iris.SlugSpike"


class HomeRoute(router.Route):
    path = "/"
    form = "iris.HelloWorld"

    def meta(self, **kwargs):
        return {"title": "Iris"}
