<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2026 Empiria -->

# Iris

*Powered by [VDO.Ninja](https://vdo.ninja).*

**Short meeting links that just work.** Send a client `meet.example.com/dk2wjd9d`,
and they are in a high-quality video call one click later: no account, no
install, no long URL.

- **Short, memorable links.** Iris builds on [VDO.Ninja](https://vdo.ninja)'s
  peer-to-peer rooms and adds a short, Google-Meet-style address plus
  admin-managed settings. Easy to say, paste and trust.
- **Peer-to-peer calls.** Rooms are VDO.Ninja rooms, so media goes directly
  between participants. Iris never forces a relay.
- **No accounts for guests.** Clients open the link and join. Only your admins
  sign in.
- **Your call settings, applied for you.** Admins control the quality profile
  once (for example sharp screen sharing, AV1 first) and every call uses it.
- **Works well across browsers.** The room opens inside the Iris page where
  that is smooth, and hands off straight to VDO.Ninja where that is better.
- **Self-hostable.** An [Anvil](https://anvil.works) app, Python on both client
  and server, no local build step. Run it on anvil.works, or on your own server
  with the open-source anvil-app-server. Nothing specific to Empiria lives in the
  code, so anyone can run their own copy.

> **Read the story:** [Why I use VDO Ninja for video calling and screen
> sharing](https://empiria.co.uk/blog/vdo_ninja/), the Empiria blog post behind
> Iris.

[Empiria](https://empiria.co.uk) runs its instance at meet.empiria.co.uk.

## Who it is for

An admin creates a link, the client opens it, and both land in a
peer-to-peer VDO.Ninja call with your call settings already applied. The client
never sees the query string.

## How it works

### Admins

Admins open the app root (`/`; `/admin` is an alias, and the older `/staff`
still works for existing bookmarks) and sign in with an email and password.
Sign-up is off: admin accounts are created by a deployer (see
[Install](#install)). A signed-in admin can give a link an optional title and
create it. The link is copied to the clipboard, and can be copied again from
the page.

Each one-off link is a recorded `room` row with its own slug and a separate
random VDO.Ninja room name. VDO.Ninja rooms are created on demand by name, so
that unguessable room name, returned only by the server lookup, is what stops
someone inventing a slug and reaching a room. It also means a link can be
revoked (set the row inactive) and its creator is recorded.

### Clients

A client opens `/<slug>` with no account. The page looks the slug up on the
server, and shows the meeting title and a join button. An unknown or inactive
slug shows "No such meeting". Joining hands the client to the VDO.Ninja room
built from the call-settings profile.

Media stays peer to peer. Iris never sets `&meshcast` or forces a relay, and
refuses a profile that does (see below).

### Iframe or redirect hand-off

On most browsers the room opens in an iframe inside the Iris page, so the short
link stays in the address bar. Some browsers get a top-level redirect to the
VDO.Ninja address instead:

- **Brave.** Its Shields restrict the third-party storage a room uses inside an
  iframe, so the room would ask for the participant's name again. Going to
  VDO.Ninja directly avoids that. Brave can't be told from Chrome by its user
  agent, so Iris asks the browser (`navigator.brave.isBrave()`).
- **Safari on iOS (iPhone and iPad) and in-app browsers** (Facebook, Instagram,
  LinkedIn, Snapchat, WeChat, Line, Android WebViews and similar). They are
  sent to the room directly, which is the safe route on these browsers. An
  in-app browser that Iris doesn't recognise is treated as the browser it
  imitates.
- Any browser Iris can't classify also redirects.

The rule lives in `client_code/services/handoff.py`. The embed sets
`referrerpolicy="strict-origin-when-cross-origin"` and allows camera,
microphone, autoplay and display capture.

### The call-settings profile

The profile is the VDO.Ninja parameter string applied to every join, for
example `ssq=-1&sharperscreen&rbr=50000&trb=50000&crb&codec=av1,vp9,vp8,h264&q=0`
(tuned for sharp screen sharing). It is stored per deployment in the `setting`
table, with these keys:

| Key | Meaning | Default |
|-----|---------|---------|
| `vdo_profile` | Parameter string applied to every join | empty (VDO.Ninja's own defaults) |
| `vdo_origin` | VDO.Ninja host to use, `https://...` (`http` only for loopback) | `https://vdo.ninja` |
| `vdo_profile_extra_keys` | Extra profile keys to allow, comma-separated | none |
| `vdo_salt` | Reserved for permanent rooms (planned) | none |

There is no settings page yet: add or edit these rows in the Data Tables
editor. The profile is checked against an allowlist of known safe VDO.Ninja
parameters (`ALLOWED_NAMES` in `client_code/services/vdo.py`: video and
screen-share quality, bitrate, codec, audio and cosmetic keys). An unknown key,
a repeated key, a key Iris sets itself (`room`, `label`, `salt`, `hash`,
`password` and their aliases) or a media-path or server override (`meshcast*`,
`relay*`, `wss`, `turn`, `stun`, `proxy`, `push`, `privacy`, `tcp` and similar)
is refused with an error naming the key, and a bad stored value shows the
client "This meeting is not set up correctly". To allow another key for one
deployment, add an optional `vdo_profile_extra_keys` row to the `setting`
table, a comma-separated list such as `fullscreen,avatar`. It never lifts a
refusal. To allow a key for everyone, add it to `ALLOWED_NAMES`. A self-hosted VDO.Ninja is supported through `vdo_origin`.

VDO.Ninja hashes room names with the host it is served from, so changing
`vdo_origin` puts every room in a different namespace.

## Install

Iris is an Anvil app, and Anvil apps run in two places. Pick whichever suits
you. **You do not need an Anvil account to self-host.** Start by cloning this
repo. For the Anvil side of each step, follow the links to Anvil's own docs.

### Route A: hosted on anvil.works

Needs an [Anvil](https://anvil.works) account. This route follows Anvil's
documented steps and has not been re-run for this README.

1. **Create the app from this repo** (see Anvil's
   [version control docs](https://anvil.works/docs/version-control)).
2. **Add the dependencies** in the editor
   ([dependencies docs](https://anvil.works/docs/deployment/dependencies)):
   `routing` v0.7.0 and `anvil-reactive` v0.1.4 (repo
   `github.com/anvilistas/reactive`). Dependency ids are generated per app, so
   they can't be copied from `anvil.yaml`.
3. **Resolve the [Data Tables](https://anvil.works/docs/data-tables) schema**
   (`room`, `setting`, `users`) in the editor. Pushing a schema change doesn't
   apply it, so resolve it once per
   [environment](https://anvil.works/docs/deployment/environments).
4. **Set the [secrets](https://anvil.works/docs/workflows/security/encrypting-secret-data).**
   Secret values can't be copied between apps, so re-enter them. Iris needs
   `iris_admin_email` and optionally `iris_admin_password`. The earlier names
   `iris_staff_email` and `iris_staff_password` are still read as a fallback.
5. **Create the first admin user.** Sign-up is off, so
   `scripts/CreateAdmin.py` is the only way the first account comes to exist,
   and it refuses to run once an admin user exists. Press Run on `CreateAdmin` in
   the editor, read its output, then delete the password secret. With no
   password set, a random one is printed once on a line
   `generated password: ...`.
6. **Set the profile:** add `vdo_profile` (and, for your own VDO.Ninja,
   `vdo_origin`) rows to the `setting` table.
7. **Add a [custom domain](https://anvil.works/docs/deployment/custom-domains)**,
   then check a cold load of `/<slug>` on it (see
   [Status and known limits](#status-and-known-limits)).

### Route B: self-hosted with anvil-app-server

No Anvil account needed. Iris runs on the open-source
[anvil-app-server](https://github.com/anvil-works/anvil-runtime). The local
stack (`Containerfile` and `justfile`) is the working example, and is the part
that has been exercised.

**On the local stack.** `just build` fetches the dependency apps at the tags
pinned in `anvil.yaml` (no login) and builds an image with `anvil-app-server`
1.17.0. `just up` runs it with:

- `--app /srv/<package_name>` and a `--dep-id <id>=<package>` per dependency.
  `uv run --script tools/anvil_deps.py --dep-id-args` prints them from
  `anvil.yaml`, so there is no editor step. Run `just fresh` after a dependency
  or `package_name` change.
- `--data-dir /data` on a named volume, so the database survives `just down` and
  `just up` (`just fresh` discards it).
- `--auto-migrate --ignore-invalid-schema`: the first boot creates the Data
  Tables schema from `anvil.yaml`, so there is no resolve step.
- `--origin http://localhost:<port> --port 3030`: the origin must be the URL the
  browser uses.
- `--uplink-key`, a fixed development value.

Packages in `server_code/requirements.txt` are installed into the image. Create
the first admin with `just create-admin you@example.com` (or `--dev`), which
runs `scripts/CreateAdmin.py` over the uplink; a generated password is in
`just logs`. Then add the `vdo_profile` rows to the `setting` table.

**Production self-hosting is untested.** Nobody has yet run Iris this way beyond
the local stack, so treat the following as a starting point:

- The `Containerfile` is for loopback only and bakes in the well-known
  `dev-uplink` key. Use your own key and don't publish the port beyond the
  machine.
- Put a TLS reverse proxy (with websocket support) in front, and set `--origin`
  to the public `https://` URL.
- Keep and back up the database volume.
- For the first admin, `scripts/CreateAdmin.py` also reads `IRIS_ADMIN_EMAIL`
  and `IRIS_ADMIN_PASSWORD` from the environment, and `tools/create_admin.py`
  honours `IRIS_UPLINK_URL` and `IRIS_UPLINK_KEY`, but only for a `ws://` URL on
  localhost, so run it on the server or through an SSH tunnel. Untested against
  a non-development server.
- Iris reads secrets only in `CreateAdmin`, which falls back to the environment,
  so no secrets are needed to start.

## Local development

Install [`just`](https://github.com/casey/just), [`uv`](https://docs.astral.sh/uv/),
`git` and `anvil-cli`. The stack recipes also need rootless
[podman](https://podman.io).

```sh
just setup     # once per clone: git hooks, tools, Playwright chromium
just deps      # fetch the dependency apps (no Anvil login needed)
just verify    # lint, type-check, anvil validate, starter-leftovers check
just unit      # hermetic server-side tests
```

The local stack runs the app in the open-source anvil-app-server:

```sh
just build     # build the app-server image
just up        # start the stack
just seed      # seed dev accounts and a known meeting over the dev uplink
just e2e       # browser tests (pytest-playwright) against the running stack
just down      # stop it; `just fresh` starts again with an empty database
```

The stack publishes a **random free loopback port**, so several checkouts and
other projects can run at once. `just up` writes the URL to `.anvil/stack-url`
and `python3 tools/stack_url.py` prints it. Set `IRIS_URL` to point the tools at
another stack.

The unit and e2e suites are kept apart and are never collected in one pytest
run: `tests/unit` is hermetic and needs no stack, and `tests/e2e` drives a real
browser against the live stack. `just host-check` runs every podman-side step
in order and writes `.anvil/host-check.txt`.

Run `just` to list every recipe. `just verify` is the gate before a commit.

## Project layout

- `anvil.yaml`: app config, dependencies, services and the Data Tables schema
- `client_code/`: forms (`Admin`, `Join`, `MeetingFrame`), the routes and
  `services/` (hand-off, VDO.Ninja URL rules, slugs, models). Client code runs
  on Skulpt, and is imported as `iris.*`
- `server_code/`: server modules (`meetings.py`, `auth.py`, `health.py`)
- `scripts/CreateAdmin.py`: creates the first admin user
- `theme/`: colour parameters and `assets/theme.css`, which holds all styling
- `tools/`: dependency fetch, local seeding, the leftovers check and helpers
- `tests/unit/`, `tests/e2e/`: the two test suites
- `justfile`, `Containerfile`: checks and the local stack
- `pyproject.toml`, `uv.lock`: dev and test tooling only, not used by the app

## Status and known limits

**Built:** admin sign-in, one-off links, the client join page, the iframe and
redirect hand-off, and the call-settings profile.

**Planned:** permanent named rooms (for example `/infinite-worlds`) protected by
a passphrase, and the admin tools to manage them. The `room` table already has
a `kind` column for them. Expiring or one-time links, invites, a join audit and
a waiting room are outside v1.

**Known limits:**

- A cold load of `/<slug>` has been verified on the local stack
  (anvil-app-server). Check it on your own domain, hosted or self-hosted, before
  you rely on it.
- Self-hosting is exercised only as the local development stack. Running
  anvil-app-server in production (TLS, your own uplink key, backups) has not been
  tried.
- Safari on iOS and in-app browsers are redirected rather than embedded, because
  the iframe behaviour there has not been tested.
- There is no settings page yet: edit the `setting` rows in the Data Tables
  editor.
- Iris is MIT-licensed. See [Licence](#licence).

## Licence

Iris is released under the [MIT licence](LICENSE), copyright 2026 Empiria.

VDO.Ninja is a separate project by Steve Seguin, licensed under AGPL-3.0. Iris
links to VDO.Ninja and does not distribute its code.

## Credits

Iris is powered by [VDO.Ninja](https://vdo.ninja) by Steve Seguin (AGPL-3.0)
and built on [Anvil](https://anvil.works), with the
[routing](https://github.com/anvil-works/routing) (MIT) and
[anvil-reactive](https://github.com/anvilistas/reactive) (MIT) dependencies.
Full credits are in [CREDITS.md](CREDITS.md).

Iris is an independent project. It is not affiliated with, or endorsed by,
VDO.Ninja.

## Contributing

Conventions, constraints (the server and the Skulpt client run different
Python) and the checks to run are in [AGENTS.md](AGENTS.md). Run `just verify`
and `just unit` before sending a change.
