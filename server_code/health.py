import anvil.server


@anvil.server.callable
def ping():
    """Return "pong" to prove the client-to-server path works.

    It carries no data, changes none and needs no sign-in. That is why it has
    no permission check, unlike any callable that returns or modifies data.
    """
    return "pong"
