# AGENTS.md

Guidance for coding agents working in this repository. `CLAUDE.md` is a symlink to this file.

## Project

Iris gives short, Google-Meet-style meeting links that open [VDO.Ninja](https://vdo.ninja) rooms. Empiria's instance will serve them at meet.empiria.co.uk. The repo must also work for anyone deploying their own copy, so keep Empiria-specific values (domains, secrets, account ids) out of code and in config or secrets.

Iris is an [Anvil](https://anvil.works) app: Python on both client and server, with no local build step.

## Layout

- `anvil.yaml`: app config. `package_name` is `app`, startup is the `startup` module, and the services are Data Tables and Secrets.
- `client_code/startup.py`: entry point. It launches the session, which starts the router.
- `client_code/globals.py`: the `session` object (router lifecycle).
- `client_code/services/routes.py`: route classes for the `routing` dependency.
- `client_code/HelloWorld/`: placeholder home form (HTML template).
- `server_code/`: server modules. Server-side packages go in `requirements.txt`.
- `theme/`: `parameters.yaml` (colour scheme), `assets/theme.css` (design tokens and all styles), `templates.yaml` (empty: there are no theme page templates).

Dependencies (in `anvil.yaml`): `routing` v0.3.5. Nothing else. Add a dependency only when code needs it, and add it through the Anvil IDE (Settings → Dependencies), not by hand: `dep_id` values are generated per app and can't be copied between apps.

## Remotes

`production` is the live Anvil app. Never push to it. Work on branches, push to `origin`, and open PRs against `main`.

## Runtime constraints

- **Server** (`server_code/`) runs CPython with base `python310-minimal`. Don't use 3.10+ syntax: no `X | None` unions, no `match`/`case`, no `ExceptionGroup`, no `tomllib`, no parenthesised context managers.
- **Client** (`client_code/`) runs on Skulpt, not CPython. Don't use `from typing import ...` (the module doesn't exist) or subscripted generics such as `list[int]`, `dict[str, str]` or `Optional[str]`, which fail at runtime. Plain annotations like `: str` and `-> None` are fine.
- The server loads every `client_code/` module except forms, so a class defined in client code exists on both sides. Forms are client-only.

## Imports

- The top-level package is `app` (the `package_name`): `from app.services import routes`.
- Never write `from client_code.X` or `from server_code.X`. Neither is a real package, so the import always fails.
- Client code can't import server modules. On the server, both trees are flattened into one namespace, so server modules can import client modules as siblings.
- Inside `@anvil.server.server_method` bodies, import server-only modules within the method, using the absolute `from app.X` form.
- Import dependency submodules by their full path, e.g. `from anvil_extras.logging import Logger`.

## Architecture rules

- **Forms are UI only:** rendering, input, event handling, navigation and validation feedback. Keep business rules, database access and calculations out of them.
- **Server modules hold the logic:** business rules, data validation, database operations, external calls. Expose them to the client with `@anvil.server.callable`.
- **Authorise on the server.** Every callable that modifies data or returns sensitive data must check permissions server-side. Client-side checks are for hiding UI only.
- **Data access goes through model classes**, never raw `app_tables` calls from forms or callables.
  - Models live in `client_code/services/model/`, whatever the table's access settings.
  - A model subclasses `app_tables.<table>.Row` with `buffered=True, attrs=True`.
  - On a buffered row, `update()` only stages changes, so keep the `.save()` that follows it.
  - Put `@anvil.server.server_method` on any model method that touches `app_tables`. On a classmethod, put it before `@classmethod`.
  - Name tables in singular `snake_case`, and name each model class after its table in `PascalCase`.
- Pass rows and model objects through callables, not dict copies, unless you've measured a serialisation problem.
- Table schemas can live in `anvil.yaml` under `db_schema`. On anvil.works, pushing a schema change doesn't apply it: someone has to resolve it in the IDE, for each environment.
- No global mutable state shared across forms. For new client state, use the anvilistas `reactive` library (`from anvil_reactive.main import signal, render_effect, bind`). Use exactly that import path, and don't trust context7 docs for this library. `reactive` (anvil-reactive, app id `N7KFE4YBWMGWJ5OX`) is a required dependency, but it hasn't been added yet: it's waiting to be added in the IDE. Don't hand-write its `anvil.yaml` entry.

## Routing and URLs

- Navigate with the `routing` module (`from routing import router`). Don't call `open_form()` for navigation.
- Routing-library path routes are client-side only. On a private-link dev origin, a cold visit to `/<path>` returns 404. Meeting links are always cold visits, so either serve them with `@anvil.server.route`, or point them at the app root with a query parameter and redirect on the client. Test a cold load on the real origin before relying on path routes. This was seen with a later routing version than the v0.3.5 pinned here.
- Write HTTP endpoints with `@anvil.server.route`. `@anvil.server.http_endpoint` is legacy, and it serves under `/_/api/`.
- For `/.well-known/` paths, use `@anvil.server.wellknown_endpoint("/name")`, giving the path without the `/.well-known` prefix. `route` and `http_endpoint` return 404 there.

## Embedding VDO.Ninja

Anvil sends `Referrer-Policy: no-referrer` (as a header and a meta tag; this has been seen on private-link dev URLs), so embedded iframes send no `Referer`, and some embeds refuse to load without one (YouTube is the known case). Give any VDO.Ninja `<iframe>` an explicit `referrerpolicy="strict-origin-when-cross-origin"`. It also needs `allow="camera; microphone; autoplay; display-capture"`, because the room uses those browser features. If you redirect to VDO.Ninja instead of embedding it, neither point applies.

## Forms and theming

Iris builds its UI from HTML form templates and HTML components. **Don't use Material 3 (M3)**: don't add the `m3` dependency theme, M3 components (`form:dep_…:_Components.*`), M3 roles or `--anvil-m3-*` variables. Iris has no dependency theme, so `theme/assets/theme.css` is the whole look.

- Author every form as `form_template.html`, never `form_template.yaml`. To convert a YAML form, run `anvil convert-template <form_template.yaml>` rather than rewriting it by hand, then strip any M3 components it brings in.
- Write markup as plain HTML elements styled with `iris-*` classes from `theme.css`. Use `<anvil-component>` only where you need Anvil behaviour on that element, such as `bind:`/`writeback:` on an input or an Anvil component's events.
- Naming: a plain HTML element gets `anvil:name="x"` and is reached through `self.dom_nodes["x"]`. An `<anvil-component>` gets plain `name="x"` and is reached as `self.x`. Using `anvil:name` on an `<anvil-component>` leaves `self.x` undefined.
- Wire DOM events on plain elements with `anvil:on-dom:click="self._handler"`. In the handler, read `event.target`: `event.currentTarget` is null by the time the handler runs.
- Use `<button type="button">` for anything that navigates in-app. A raw `<a href="#">` with a click handler undoes the router's `navigate()`. Keep `<a href>` for real links.
- Page forms are opened by the router. A page that the router injects into a template is `<anvil-form container="ColumnPanel">`, never `layout=`. A form with no `<anvil-form>` root is a plain `HtmlComponent`. That is what `HelloWorld` uses.
- Reusable pieces are HTML-template custom components: a `form_template.html` with `custom_component: true` and its `properties:`/`events:` in YAML front matter.
- Colours live only in `theme/parameters.yaml`. `theme.css` reads them with `%color:Name%` into `--iris-*` custom properties, and every rule uses those variables. Don't hardcode colours. Keep the brand colour first in `parameters.yaml`, because Anvil uses the first colour for the browser theme colour and the loading spinner.
- Build a JS library or DOM integration as an HtmlTemplate custom component, and initialise it in `form_show`, not `__init__`.
- `anvil.js` awaits JS Promises automatically, so bind the return value instead of chaining `.then()`.

## Secrets and self-hosting

- Secret values in `anvil.yaml` are encrypted to the app and account that created them. In a fork or a fresh deployment the names survive but the values can't be read, and `get_secret` raises. Re-enter them in the new app.
- After importing the app into a new account, re-add each dependency through "Add Dependency".

## Checks

- After editing any Anvil file (`anvil.yaml`, form templates, `client_code/**/*.py`, `server_code/**/*.py`), run `anvil --json validate <path>` and fix any reported `issues`. Run `anvil validate .` before handing off.
- `validate` needs the dependency cache, so run `anvil deps fetch` first. Without the cache it reports unresolved imports for `m3`, `routing` and `anvil_extras`.
- Lint with ruff using Empiria's rule set:
  `ruff check --select E,F,I001,SIM,C4,PERF,RET,UP,C90 <files>`
  In `client_code/`, reject autofixes that bring in subscripted generics or `contextlib.suppress`: Skulpt can't run the generics, and `contextlib.suppress` is unverified there.
- Type-check with `anvil-pyright`, not plain basedpyright.
- `pytest` can't run `client_code/`. Pin server payload shapes in tests, and check client behaviour in a browser.

## Reference docs

Use context7 for Anvil API questions:

```bash
ctx7 docs /websites/anvil_works "<question>"
ctx7 docs /anvil-works/routing "<question>"
ctx7 docs /anvilistas/anvil-extras "<question>"
```

The open-source runtime, https://github.com/anvil-works/anvil-runtime, is useful for internals. It lags production slightly.
