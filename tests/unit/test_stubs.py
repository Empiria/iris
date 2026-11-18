"""The test harness itself: recording decorators, fake tables, users, iris package."""

import importlib
import sys

import pytest
from anvil import server, users
from anvil.tables import app_tables


def _last():
    return server.registrations[-1]


def test_bare_callable_is_recorded_and_returned_unchanged():
    def func():
        return 1

    assert server.callable(func) is func
    record = _last()
    assert record.kind == "callable"
    assert record.obj is func
    assert "require_user" not in record.kwargs
    assert record.name.endswith("func")


def test_callable_with_require_user_records_the_predicate():
    def pred(user):
        return user is not None

    @server.callable(require_user=pred)
    def guarded():
        return 2

    assert guarded() == 2
    record = _last()
    assert record.kind == "callable"
    assert record.kwargs["require_user"] is pred


def test_server_method_above_classmethod_records_the_qualified_name():
    class Thing:
        @server.server_method
        @classmethod
        def look(cls):
            return "x"

    record = _last()
    assert record.kind == "server_method"
    assert record.name.endswith("Thing.look")
    assert isinstance(record.obj, classmethod)
    assert Thing.look() == "x"


def test_route_and_wellknown_keep_the_path_and_the_function():
    @server.route("/x", methods=["GET"])
    def handler():
        return "ok"

    record = _last()
    assert record.kind == "route"
    assert record.kwargs["args"] == ("/x",)
    assert record.kwargs["methods"] == ["GET"]
    assert handler() == "ok"

    @server.wellknown_endpoint("/thing")
    def well():
        return "w"

    assert _last().kind == "wellknown_endpoint"
    assert well() == "w"


def test_anvil_server_is_the_stub_and_has_no_connect():
    assert not hasattr(sys.modules["anvil.server"], "connect")


def test_permission_denied_is_an_exception():
    assert issubclass(server.PermissionDenied, Exception)


def test_app_tables_returns_the_same_table_each_time(tables):
    assert app_tables.thing is app_tables.thing
    assert app_tables.thing is not app_tables.other


def test_subclassing_row_registers_the_row_class(tables):
    class Widget(app_tables.widget.Row, buffered=True, attrs=True):
        pass

    row = app_tables.widget.add_row(name="a")
    assert isinstance(row, Widget)


def test_get_search_and_read_counts(tables):
    table = app_tables.thing
    table.add_row(slug="a", n=1)
    table.add_row(slug="b", n=1)

    assert table.get(slug="a")["n"] == 1
    assert table.get(slug="zzz") is None
    with pytest.raises(ValueError):
        table.get(n=1)
    assert len(table.search(n=1)) == 2
    assert table.reads == 4


def test_row_access_update_save_delete(tables):
    table = app_tables.thing
    row = table.add_row(slug="a", n=1)

    assert row["slug"] == "a"
    assert row.get("missing") is None
    assert row.get("missing", 5) == 5
    row["n"] = 2
    assert row.n == 2
    row.update(n=3, slug="b")
    row.save()
    assert (row.slug, row.n) == ("b", 3)
    row.delete()
    assert table.rows == []


def test_tables_fixture_clears_rows_and_reads(tables):
    assert app_tables.thing.rows == []
    assert app_tables.thing.reads == 0


def test_signed_out_by_default_and_as_user_sets_the_user(as_user, make_user):
    assert users.get_user() is None
    admin = make_user()
    as_user(admin)
    assert users.get_user() is admin
    assert admin["email"] == "admin@example.test"
    assert admin["is_admin"] is True
    as_user(None)
    assert users.get_user() is None


def test_make_user_can_be_non_admin(make_user):
    assert make_user(email="x@y.test", is_admin=False)["is_admin"] is False


def test_iris_package_resolves_both_trees():
    slugs_path = importlib.import_module("iris.services").__path__
    assert slugs_path
    health = importlib.import_module("iris.health")
    assert health.ping() == "pong"
