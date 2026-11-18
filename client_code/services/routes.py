from routing import router


class HomeRoute(router.Route):
    path = "/"
    form = "iris.HelloWorld"

    def meta(self, **kwargs):
        return {"title": "Iris"}
