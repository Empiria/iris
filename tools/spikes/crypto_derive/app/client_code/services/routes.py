from routing import router


class DeriveSpikeRoute(router.Route):
    """At the app root: a cold visit to a client-only path route 404s."""

    path = "/"
    form = "iris.DeriveSpike"

    def meta(self, **kwargs):
        return {"title": "Derive spike"}
