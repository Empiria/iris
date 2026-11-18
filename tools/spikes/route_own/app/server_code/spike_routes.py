import anvil.server
from anvil.tables import app_tables

# Calls are counted in a table, not a module variable: the route handler and the
# callables are not guaranteed to share one Python process or its globals.


def _lookup(slug):
    app_tables.spike_call.add_row(slug=slug)
    if slug == "spikeslug":
        return {"slug": slug, "value": "spike-value-1"}
    return None


@anvil.server.callable
def spike_calls():
    return [row["slug"] for row in app_tables.spike_call.search()]


@anvil.server.callable
def spike_reset():
    app_tables.spike_call.delete_all_rows()


# /staff is declared before /:slug. Declared the other way round, /:slug answered
# /staff as well.
@anvil.server.route("/staff")
def staff_page(**params):
    return anvil.server.HttpResponse(
        200,
        "staff-route-answered",
        headers={"Content-Type": "text/html; charset=utf-8"},
    )


@anvil.server.route("/:slug")
def slug_page(slug, **params):
    found = _lookup(slug)
    return anvil.server.AppResponder(data={"lookup": found}).load_app()


@anvil.server.route("/raw/:slug")
def raw_page(slug, **params):
    found = _lookup(slug)
    if found is None:
        return anvil.server.HttpResponse(
            404,
            "not found",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
    return anvil.server.HttpResponse(
        200,
        "<p>raw:{}</p>".format(found["value"]),
        headers={"Content-Type": "text/html; charset=utf-8"},
    )
