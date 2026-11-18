from routing import router


class StaffRoute(router.Route):
    path = "/staff"
    form = "iris.Staff"

    def meta(self, **kwargs):
        return {"title": "Iris staff"}


class HomeRoute(router.Route):
    path = "/"
    form = "iris.HelloWorld"

    def meta(self, **kwargs):
        return {"title": "Iris"}
