<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2026 Empiria -->

# AGENTS.md

Guidance for coding agents working in this repository. `CLAUDE.md` is an untracked local symlink to this file. It is listed in the git exclude file (`git rev-parse --git-path info/exclude`) and `just setup` creates it. Never commit it.

## Project

Iris gives short, Google-Meet-style meeting links that open [VDO.Ninja](https://vdo.ninja) rooms. Empiria's instance will serve them at meet.empiria.co.uk. The repo must also work for anyone deploying their own copy, so keep Empiria-specific values (domains, secrets, account ids) out of code and in config or secrets.

Iris is an [Anvil](https://anvil.works) app: Python on both client and server, with no local build step.

## Layout

- `anvil.yaml`: app config. `package_name` is `iris`, startup is the `startup` module, and the services are Data Tables and Secrets.
- `client_code/startup.py`: entry point. It clears the router cache and launches the router.
- `client_code/services/routes.py`: route classes for the `routing` dependency. `/` is the admin page (`/admin` and the older `/staff` are aliases), and every other path is a meeting slug.
- `server_code/`: server modules. Server-side packages go in `requirements.txt`.
- `scripts/CreateAdmin.py`: the first-admin script (it still reads the old `iris_staff_*` secrets and `IRIS_STAFF_*` variables as a fallback) and the only caller of `signup_with_email`. `just create-admin` launches it on the local stack, and a hosted app runs it from the Anvil editor. `anvil validate` rejects a `scripts` path, so `just validate` skips it.
- `server_code/health.py`: provides the `ping` callable the local stack tests use.
- `theme/`: `parameters.yaml` (colour scheme), `assets/theme.css` (design tokens and all styles), `templates.yaml` (empty: there are no theme page templates).
- `tools/`: `anvil_deps.py` fetches the dependency apps with no login. `leftovers.py` is the starter-leftovers check. It also reads an optional untracked `.leftovers-local` file of extra regexes, one per line. `dev_seed.py` seeds the local stack. `stack_url.py` finds the local stack's URL (see Local stack).
- `tests/`: `unit/` holds server-side unit tests, `e2e/` holds pytest-playwright tests against the live local stack. The two are never collected together.
- The Phase 2 spike tooling (`tools/spike.py`, `tools/spikes/`, `tests/unit/test_spike.py`, the `spike` recipes) is gone from the tree. The annotated tag `spikes-archive` keeps it: `git checkout spikes-archive -- tools/spike.py tools/spikes tests/unit/test_spike.py`.
- `justfile`: the check, stack and test recipes (see Checks).
- `.github/workflows/ci.yml`: CI runs `just verify` (with anvil-pyright from npm) on pushes to `main` and on pull requests. The e2e suite is not run there.
- `REUSE.toml`: the SPDX cover for files that can't hold a header (see `just spdx` under Checks).
- `SECURITY.md`, `CONTRIBUTING.md`: how to report a vulnerability, and how to send a change.
- `client_code/ForgotPassword/` is the sign-in form's password-reset entry; `services/password_reset.py` calls the Users service's own reset.
- `Containerfile`: the local anvil-app-server image.
- `pyproject.toml` and `uv.lock`: dev and test tooling only. The Anvil app does not use them.

Dependencies (in `anvil.yaml`): `routing` v0.7.0 and `anvil-reactive` v0.1.4 (repo `github.com/anvilistas/reactive`, package `anvil_reactive`, app id `N7KFE4YBWMGWJ5OX`). Nothing else. Add or bump a dependency only when code needs it, and do it through the Anvil IDE (Settings → Dependencies), not by hand: `dep_id` values are generated per app and can't be copied between apps. `tools/anvil_deps.py` reads the pinned tag from `anvil.yaml`, so an IDE bump is picked up on the next `just deps`.

## Remotes

The maintainer's own work is merged straight to `main` with no pull request (outside contributions arrive as pull requests, which the maintainer merges). Work is merged to `main`, and `main` is pushed to `origin` and to `production`. `production` is the live Anvil app, so agents never push to it. The lead does that.

## Runtime constraints

- **Server** (`server_code/`) runs CPython with base `python310-minimal`. Don't use 3.10+ syntax: no `X | None` unions, no `match`/`case`, no `ExceptionGroup`, no `tomllib`, no parenthesised context managers.
- **Client** (`client_code/`) runs on Skulpt, not CPython. Don't use `from typing import ...` (the module doesn't exist) or subscripted generics such as `list[int]`, `dict[str, str]` or `Optional[str]`, which fail at runtime. Plain annotations like `: str` and `-> None` are fine.
- The server loads every `client_code/` module except forms, so a class defined in client code exists on both sides. Forms are client-only.

## Imports

- The top-level package is `iris` (the `package_name`): `from iris.services import routes`.
- Never write `from client_code.X` or `from server_code.X`. Neither is a real package, so the import always fails.
- Client code can't import server modules. On the server, both trees are flattened into one namespace, so server modules can import client modules as siblings.
- Inside `@anvil.server.server_method` bodies, import server-only modules within the method, using the absolute `from iris.X` form.
- Import dependency submodules by their full path, e.g. `from anvil_reactive.main import signal`.

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
- No global mutable state shared across forms. For new client state, use the anvilistas `reactive` library (`from anvil_reactive.main import signal, render_effect, bind`). Use exactly that import path, and don't trust context7 docs for this library. `reactive` (anvil-reactive, app id `N7KFE4YBWMGWJ5OX`) is a dependency now.

## Routing and URLs

- Navigate with the `routing` module (`from routing import router`). Don't call `open_form()` for navigation.
- Routing-library path routes are client-side only. On a private-link dev origin, a cold visit to `/<path>` returns 404. Meeting links are always cold visits, so either serve them with `@anvil.server.route`, or point them at the app root with a query parameter and redirect on the client. The 404 was seen on a private-link dev origin with a routing version later than v0.3.5. Re-test a cold load on the real origin with the pinned v0.7.0 before relying on path routes.
- Write HTTP endpoints with `@anvil.server.route`. `@anvil.server.http_endpoint` is legacy, and it serves under `/_/api/`.
- For `/.well-known/` paths, use `@anvil.server.wellknown_endpoint("/name")`, giving the path without the `/.well-known` prefix. `route` and `http_endpoint` return 404 there.

## Embedding VDO.Ninja

Anvil sends `Referrer-Policy: no-referrer` (as a header and a meta tag; this has been seen on private-link dev URLs), so embedded iframes send no `Referer`, and some embeds refuse to load without one (YouTube is the known case). Give any VDO.Ninja `<iframe>` an explicit `referrerpolicy="strict-origin-when-cross-origin"`. It also needs `allow="camera; microphone; autoplay; display-capture"`, because the room uses those browser features. If you redirect to VDO.Ninja instead of embedding it, neither point applies.

## Forms and theming

Iris builds its UI from HTML form templates and HTML components. **Don't use Material 3 (M3)**: don't add the `m3` dependency theme, M3 components (`form:dep_…:_Components.*`), M3 roles or `--anvil-m3-*` variables. Iris has no dependency theme, so `theme/assets/theme.css` is the whole look.

- Author every form as `form_template.html`, never `form_template.yaml`. To convert a YAML form, run `anvil convert-template <form_template.yaml>` rather than rewriting it by hand, then strip any M3 components it brings in.
- Write markup as plain HTML elements styled with `iris-*` classes from `theme.css`. Use `<anvil-component>` only where you need Anvil behaviour on that element, such as `bind:`/`writeback:` on an input or an Anvil component's events.
- Naming: to reach a plain HTML element's DOM node, give it `anvil:dom-node="x"` and use `self.dom_nodes["x"]`. `anvil:name="x"` on a plain element does something else: the element becomes a child `HtmlComponent` reached as `self.x` (for its `classes` and `style` helpers), and `self.dom_nodes["x"]` raises `KeyError`. An `<anvil-component>` gets plain `name="x"` and is reached as `self.x`. Using `anvil:name` on an `<anvil-component>` leaves `self.x` undefined. A unit test checks every `dom_nodes` lookup in form code against the template's `anvil:dom-node` names.
- Wire DOM events on plain elements with `anvil:on-dom:click="self._handler"`. In the handler, read `event.target`: `event.currentTarget` is null by the time the handler runs.
- Use `<button type="button">` for anything that navigates in-app. A raw `<a href="#">` with a click handler undoes the router's `navigate()`. Keep `<a href>` for real links.
- Page forms are opened by the router. A page that the router injects into a template is `<anvil-form container="ColumnPanel">`, never `layout=`. A form with no `<anvil-form>` root is a plain `HtmlComponent`.
- Reusable pieces are HTML-template custom components: a `form_template.html` with `custom_component: true` and its `properties:`/`events:` in YAML front matter.
- Colours live only in `theme/parameters.yaml`. `theme.css` reads them with `%color:Name%` into `--iris-*` custom properties, and every rule uses those variables. Don't hardcode colours. Keep the brand colour first in `parameters.yaml`, because Anvil uses the first colour for the browser theme colour and the loading spinner.
- Build a JS library or DOM integration as an HtmlTemplate custom component, and initialise it in `form_show`, not `__init__`.
- `anvil.js` awaits JS Promises automatically, so bind the return value instead of chaining `.then()`.

## Secrets and self-hosting

- Secret values in `anvil.yaml` are encrypted to the app and account that created them. In a fork or a fresh deployment the names survive but the values can't be read, and `get_secret` raises. Re-enter them in the new app.
- After importing the app into a new account, re-add each dependency through "Add Dependency".

## Checks

- Run `just setup` once per clone or worktree. It is idempotent: it creates the `CLAUDE.md` link, the hooks and the tools, and never needs an Anvil login.
- Playwright's browsers live in the gitignored `.anvil/ms-playwright`, not under `$HOME`, so the e2e tests find them whatever HOME is. The justfile exports `PLAYWRIGHT_BROWSERS_PATH` with that path, and `tests/e2e/conftest.py` sets it for a bare `pytest` run. A value you set yourself wins. `just setup` installs chromium there, which needs network the first time.
- `just deps` fetches the dependency apps from their public GitHub repos at the tags pinned in `anvil.yaml` into the gitignored `.anvil/` directory. It needs no Anvil login and doesn't write to `.git/config`. `validate` and `check` run it for you.
- `just stubs` is a note only: anvil-pyright bundles the Anvil stubs, so never wire in a `.stubs/` directory.
- `just lint` runs ruff with Empiria's rule set from `.ruff.toml`. In `client_code/`, reject autofixes that bring in subscripted generics or `contextlib.suppress`: Skulpt can't run the generics, and `contextlib.suppress` is unverified there. `just format` formats.
- `just check` type-checks with `anvil-pyright`, not plain basedpyright.
- `just validate` runs `anvil validate` on `anvil.yaml`, `client_code`, `server_code` and `theme`, one path at a time. It doesn't validate `tools/`, `tests/` or `scripts/`.
- `just density` prints comment-to-code density as a prompt to re-read, not a gate. It needs `MNEMOSYNE_VAULT` set to a vault checkout that holds `technologies/python/tools/comment_ratio.py`, and fails with a message if it is unset.
- `just leftovers` checks that nothing from the starter has come back. It also applies any extra patterns in the optional untracked `.leftovers-local` file. `just setup` lists that file in the git exclude file, and it is never committed.
- `just spdx` fails if a tracked file has neither an `SPDX-License-Identifier: MIT` and `Copyright (c) 2026 Empiria` header nor a cover in `REUSE.toml`. Give every new file a header (`#` comment in py, justfile and the like, `/* */` in css, `<!-- -->` in md). JSON, lock files, `anvil.yaml`, `.anvil_editor.yaml`, `theme/*.yaml` and every `form_template.html` are covered by `REUSE.toml` instead, because they can't hold a comment or the Anvil editor rewrites them.
- `just verify` runs lint, format-check, check, validate, leftovers, spdx and unit. It is the gate before handing off.
- `just unit` runs the server-side unit tests. They need no stack, but a few read source files (`tests/e2e/*.py`, `tools/`) to keep copies of constants in step.
- `just lock` re-resolves `uv.lock` after a change to the dev dependencies in `pyproject.toml`. Use it rather than `uv lock` by hand.
- SPDX policy: every tracked file carries an `SPDX-License-Identifier: MIT` and `Copyright (c) 2026 Empiria` header, or is listed in `REUSE.toml`. Don't list a file there if it can hold a comment.
- After editing any Anvil file (`anvil.yaml`, form templates, `client_code/**/*.py`, `server_code/**/*.py`), run `anvil --json validate <path>` and fix any reported `issues`.
- `pytest` can't run `client_code/`. Pin server payload shapes in unit tests, and check client behaviour in a browser.

### Local stack and e2e tests

`just build`, `just up`, `just down`, `just restart`, `just fresh`, `just logs`, `just seed`, `just create-admin` and `just e2e` need rootless podman and the live stack. They are host-only: they can't run in a worker sandbox, where only `deps`, `lint`, `check`, `validate`, `leftovers`, `unit` and `verify` run. The app is served on a random free loopback port (see below), and the dev uplink key `dev-uplink` is local-only. The unit and e2e suites are never collected in one pytest run (a conftest guard enforces it). `just host-check` runs every host-only step in order: setup checks, `deps` with the shared-config check, `build`, a cold boot, the loopback and dependency-id checks, `seed`, `e2e` and the lifecycle recipes. It stops at the first failure, writes the log and a summary to `.anvil/host-check.txt`, and leaves the stack running.

Sandbox reach of the host stack: not reachable. On 2026-11-18, a direct `curl` of the stack's `localhost` URL from a worker sandbox, with the stack up on the host, failed to connect. So `seed` and `e2e` are host-only like the other stack recipes. A sandboxed worker runs `just unit` and `just verify` and leaves the stack recipes to the host or the lead. A desk worker whose `just` commands run outside the sandbox can run them, and can reach the stack through the sandbox proxy (`curl --noproxy '' -x "$HTTP_PROXY"`) with the stack's `localhost:<port>` allowed.

Host results, 2026-11-18, `just host-check` on podman 6.2.0: `just build` took 2 s with a warm cache, and a cold boot on a clean database answered 200 in 9 s. The port was published on `127.0.0.1` only. The four `--dep-id` flags match `anvil.yaml`, and the runtime user finds the baked-in app-server JAR with no download. `just seed` prints `seed: uplink round trip ok (ping -> pong)` twice. `just e2e` passes, before and after `just fresh`. The first run failed at `e2e` with `KeyError: server_status`, because the page used `anvil:name` where it needed `anvil:dom-node` (see Forms and theming). After the fix, the host run passed.

- **No fixed host port.** Several stacks (other checkouts, other projects) run at once, so `just up` picks a free loopback port when it creates the container, publishes it (`-p 127.0.0.1:<port>:3030`; the app inside the container still listens on 3030) and passes `--origin http://localhost:<port>`, so the page loads its assets and websocket from the published port (without the origin the page shows the Anvil error banner). It writes the resolved URL, e.g. `http://localhost:41234/`, to the git-ignored `.anvil/stack-url`. A stopped container keeps its port, and if something else has taken it, `up` recreates the container on a new port with the database volume intact. `up`, `restart` and `fresh` rewrite the file and `down` removes it. `tools/stack_url.py` resolves the URL, first from `IRIS_URL`, then from `.anvil/stack-url`, and fails with a message saying how to start a stack if neither exists. `just seed`, `just create-admin`, `just e2e`, `tools/dev_seed.py`, `tools/create_admin.py` and a bare `uv run pytest tests/e2e` all use it. `IRIS_URL` points them at another stack, and `--base-url` still wins for pytest. `python3 tools/stack_url.py` prints the URL. No recipe needs an environment assignment, so host `just` commands are plain.
- After a dependency or `package_name` change in the IDE, run `just fresh` so the `--dep-id` and `--app` flags are regenerated. The justfile reads `package_name` from `anvil.yaml`, so a rename needs no edit there.
- An IDE save can drop the executable bit from files under `tools/`. Always run them through `uv run --script` (or `python3`), never as `./tools/x.py`.
- Each checkout gets its own container and database volume, `iris-anvil-<checkout dir>` and `iris-anvil-<checkout dir>-data`, so a stale container left by another checkout can't block this one. `IRIS_CONTAINER` (or `just ctr=NAME up`) overrides the name. Each publishes its own random port, so they run side by side. `.anvil/stack-url` is per checkout and holds the last stack started there. `just stack-reset` force-removes this checkout's container, and host-check runs it first.
- `IRIS_STACK_RETRIES` raises how long `seed` and `e2e` wait for a slow first boot (default 30 tries, 2 s apart).
- A client error shows in `just logs` as `Error report from client code:` with a traceback.

## Reference docs

Use context7 for Anvil API questions:

```bash
ctx7 docs /websites/anvil_works "<question>"
ctx7 docs /anvil-works/routing "<question>"
```

The open-source runtime, https://github.com/anvil-works/anvil-runtime, is useful for internals. It lags production slightly.
