from routing import router


class SlugFallbackRoute(router.Route):
    """No path, so Routing registers no server route for it. It is the page the
    router uses when no pathed Route matches."""

    path = None
    form = "iris.SlugSpike"
    default_not_found = True


class HomeRoute(router.Route):
    path = "/"
    form = "iris.HelloWorld"

    def meta(self, **kwargs):
        return {"title": "Iris"}
