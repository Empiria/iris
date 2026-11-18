from routing import router


class MatrixRoute(router.Route):
    """At the app root: a cold visit to a client-only path route 404s."""

    path = "/"
    form = "iris.Matrix"

    def meta(self, **kwargs):
        return {"title": "Iframe matrix"}
