# Iris

**Short meeting links that just work.** Send a client `meet.example.com/dk2wjd9d`,
and they are in a high-quality video call one click later: no account, no
install, no long URL.

- **Short, memorable links.** Iris builds on [VDO.Ninja](https://vdo.ninja)'s
  peer-to-peer rooms and adds a short, Google-Meet-style address plus
  staff-managed settings. Easy to say, paste and trust.
- **Peer-to-peer calls.** Rooms are VDO.Ninja rooms, so media goes directly
  between participants. Iris never forces a relay.
- **No accounts for guests.** Clients open the link and join. Only your staff
  sign in.
- **Your call settings, applied for you.** Staff control the quality profile
  once (for example sharp screen sharing, AV1 first) and every call uses it.
- **Works well across browsers.** The room opens inside the Iris page where
  that is smooth, and hands off straight to VDO.Ninja where that is better.
- **Self-hostable.** [Anvil](https://anvil.works) app, Python on both client
  and server, no local build step. Nothing specific to Empiria lives in the
  code, so anyone can run their own copy.

> **Read the story:** [Why I use VDO Ninja for video calling and screen
> sharing](https://empiria.co.uk/blog/vdo_ninja/), the Empiria blog post behind
> Iris.

[Empiria](https://empiria.co.uk) runs its instance at meet.empiria.co.uk.

## Who it is for

A member of staff creates a link, the client opens it, and both land in a
peer-to-peer VDO.Ninja call with your call settings already applied. The client
never sees the query string.

## How it works

### Staff

Staff open the app root (`/`; `/staff` is an alias) and sign in with an email
and password. Sign-up is off: staff accounts are created by an administrator
(see [Create the first staff user](#create-the-first-staff-user)). A signed-in
member of staff can give a link an optional title and create it. The link is
copied to the clipboard, and can be copied again from the page.

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
| `vdo_salt` | Reserved for permanent rooms (planned) | none |

There is no settings page yet: add or edit these rows in the Data Tables
editor. Profiles that force relaying or change the media path (`meshcast*`,
`relay*`, `privacy`, `private`, `icefilter`, `tcp`) or that try to set the room
or label are refused, and a bad value shows the client "This meeting is not set
up correctly". A self-hosted VDO.Ninja is supported through `vdo_origin`.

VDO.Ninja hashes room names with the host it is served from, so changing
`vdo_origin` puts every room in a different namespace.

## Install

You need an Anvil account. The steps below create your own copy of the app.

1. **Create the app from this repo.** Clone it, then either create a new Anvil
   app from the git repo, or run it yourself on
   [anvil-app-server](https://github.com/anvil-works/anvil-runtime) (the local
   stack below does this).
2. **Add the dependencies.** In the Anvil editor, Settings → Dependencies →
   "Add Dependency" for each of these. Dependency ids are generated per app, so
   they can't be copied from `anvil.yaml` into another app.
   - `routing` v0.7.0
   - `anvil-reactive` v0.1.4 (repo `github.com/anvilistas/reactive`)
3. **Resolve the Data Tables schema.** The schema is in `anvil.yaml`
   (`room`, `setting` and `users`). On anvil.works, pushing a schema change
   does not apply it: open the app in the editor and resolve it, once for each
   environment (development and production).
4. **Set the secrets.** Anvil encrypts secret values to the app and account that
   created them, so a fork or fresh deployment has the secret names but not the
   values. Re-enter them in your own app. Iris needs `iris_staff_email`, and
   optionally `iris_staff_password`, for the next step.
5. **Create the first staff user** (below).
6. **Set the profile.** Add `vdo_profile` (and, if you host VDO.Ninja yourself,
   `vdo_origin`) rows to the `setting` table.
7. **Custom domain.** Point your domain at the app using Anvil's custom domain
   settings. Meeting links are always cold visits to `/<slug>`. Check a cold load of
   `/<slug>` on your own domain once it is set up (see
   [Status and known limits](#status-and-known-limits)).

### Create the first staff user

Sign-up is off, and a browser can't run a script, so `scripts/CreateStaff.py` is
the only way the first staff account comes to exist. It refuses to run once any
staff user exists.

On a hosted app: set the `iris_staff_email` secret and, if you want to choose
the password, `iris_staff_password`. Press Run on `CreateStaff` in the Anvil
editor and read its output, then delete the password secret. With no password
set, a random one is generated and printed once, on a line
`generated password: ...`.

Locally: `just create-staff --dev`, or `just create-staff you@example.com`. A
generated password is in `just logs`.

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
- `client_code/`: forms (`Staff`, `Join`, `MeetingFrame`), the routes and
  `services/` (hand-off, VDO.Ninja URL rules, slugs, models). Client code runs
  on Skulpt, and is imported as `iris.*`
- `server_code/`: server modules (`meetings.py`, `auth.py`, `health.py`)
- `scripts/CreateStaff.py`: creates the first staff user
- `theme/`: colour parameters and `assets/theme.css`, which holds all styling
- `tools/`: dependency fetch, local seeding, the leftovers check and helpers
- `tests/unit/`, `tests/e2e/`: the two test suites
- `justfile`, `Containerfile`: checks and the local stack
- `pyproject.toml`, `uv.lock`: dev and test tooling only, not used by the app

## Status and known limits

**Built:** staff sign-in, one-off links, the client join page, the iframe and
redirect hand-off, and the call-settings profile.

**Planned:** permanent named rooms (for example `/infinite-worlds`) protected by
a passphrase, and the staff tools to manage them. The `room` table already has
a `kind` column for them. Expiring or one-time links, invites, a join audit and
a waiting room are outside v1.

**Known limits:**

- A cold load of `/<slug>` has been verified on the local stack. Check it on
  your own custom domain on a hosted app before you rely on it.
- Safari on iOS and in-app browsers are redirected rather than embedded, because
  the iframe behaviour there has not been tested.
- There is no settings page yet: edit the `setting` rows in the Data Tables
  editor.
- No licence has been chosen yet. See [Licence](#licence).

## Licence

The repo does not have a licence file yet, and one has not been chosen. Until
one is added, no licence is granted. VDO.Ninja is licensed separately
(AGPL-3.0); Iris links to it and embeds it by URL, and is not VDO.Ninja or
presented as official.

## Contributing

Conventions, constraints (the server and the Skulpt client run different
Python) and the checks to run are in [AGENTS.md](AGENTS.md). Run `just verify`
and `just unit` before sending a change.
