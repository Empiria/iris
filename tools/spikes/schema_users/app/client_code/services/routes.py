from routing import router


class SignupRoute(router.Route):
    path = "/"
    form = "iris.SignupSpike"
