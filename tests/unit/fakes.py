# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""In-memory stand-ins for Anvil Data Tables and users, for the unit suite.

Plain Python with no third-party imports. `FakeTables` plays `app_tables`: each
table is created on first use, and `app_tables.<name>.Row` is a base class whose
subclasses (declared with `buffered=True, attrs=True`) become that table's row
class, the way Anvil model classes do.
"""


class FakeRow:
    """A row. `Row` bases for each table subclass this."""

    _fake_table = None
    _is_table_base = False

    def __init_subclass__(cls, buffered=False, attrs=False, **kwargs):
        super().__init_subclass__(**kwargs)
        table = cls._fake_table
        if table is not None and not cls.__dict__.get("_is_table_base", False):
            table.row_class = cls
            cls._buffered = buffered
            cls._attrs = attrs

    def __init__(self, values=None):
        object.__setattr__(self, "_values", dict(values or {}))
        object.__setattr__(self, "deleted", False)
        object.__setattr__(self, "saves", 0)

    def __getitem__(self, column):
        return self._values[column]

    def __setitem__(self, column, value):
        self._values[column] = value

    def __getattr__(self, name):
        # Only reached when normal lookup fails, so methods and class
        # attributes win over columns.
        values = self.__dict__.get("_values")
        if values is not None and name in values:
            return values[name]
        raise AttributeError(name)

    def get(self, column, default=None):
        return self._values.get(column, default)

    def update(self, **values):
        self._values.update(values)

    def save(self):
        object.__setattr__(self, "saves", self.saves + 1)

    def delete(self):
        object.__setattr__(self, "deleted", True)
        table = self.__dict__.get("_table")
        if table is not None and self in table.rows:
            table.rows.remove(self)

    def __repr__(self):
        return f"<{type(self).__name__} {self._values!r}>"


class FakeTable:
    def __init__(self, name):
        self.name = name
        self.rows = []
        self.reads = 0
        self.row_class = None
        self.Row = type(
            "Row",
            (FakeRow,),
            {"_fake_table": self, "_is_table_base": True},
        )

    def add_row(self, **values):
        row = (self.row_class or FakeRow)(values)
        row.__dict__["_table"] = self
        self.rows.append(row)
        return row

    def _matching(self, criteria):
        return [
            row
            for row in self.rows
            if all(row._values.get(k) == v for k, v in criteria.items())
        ]

    def get(self, **criteria):
        self.reads += 1
        found = self._matching(criteria)
        if len(found) > 1:
            raise ValueError(f"{self.name}: {len(found)} rows match {criteria!r}")
        return found[0] if found else None

    def search(self, **criteria):
        self.reads += 1
        return self._matching(criteria)

    def clear(self):
        self.rows = []
        self.reads = 0


class FakeTables:
    """Stands in for `anvil.tables.app_tables`."""

    def __init__(self):
        self._tables = {}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        tables = self.__dict__["_tables"]
        if name not in tables:
            tables[name] = FakeTable(name)
        return tables[name]

    def clear(self):
        """Empty every table and zero its read count. Row classes stay."""
        for table in self._tables.values():
            table.clear()


MISSING = object()


class FakeUser:
    """A users-table row: `user["email"]`, `user["is_admin"]`."""

    def __init__(self, email="admin@example.test", is_admin=True, **extra):
        self._values = {"email": email, "is_admin": is_admin}
        # Extra columns, such as the legacy `is_staff`. Pass is_admin=MISSING
        # to model a table that has no `is_admin` column yet.
        self._values.update(extra)
        if is_admin is MISSING:
            del self._values["is_admin"]

    def __getitem__(self, column):
        return self._values[column]

    def get(self, column, default=None):
        return self._values.get(column, default)
