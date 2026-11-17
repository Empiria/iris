from routing import router


class HomeRoute(router.Route):
    path = "/"
    form = "app.HelloWorld"

    def meta(self, **kwargs):
        return {"title": "Iris"}
