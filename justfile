# Iris justfile. `just verify` is the static gate; `just unit` and `just e2e` are the tests.
#
# Sandbox rule: recipes marked [host] need rootless podman, which can't run in a
# worker sandbox. They fail fast there and name the command to run on the host.

vault := env_var_or_default("MNEMOSYNE_VAULT", env_var("HOME") + "/projects/empiria/mnemosyne")

base_url := env_var_or_default("IRIS_URL", "http://localhost:3030/")
uplink_url := env_var_or_default("IRIS_UPLINK_URL", "ws://localhost:3030/_/uplink")

# How many times the stack guard retries (2 s apart) before it gives up.
stack_retries := env_var_or_default("IRIS_STACK_RETRIES", "30")

# The app's package_name (anvil.yaml). The app is mounted at /srv/<package>.
package := "app"
img := "iris-anvil-dev"
ctr := "iris-anvil"
vol := "iris-anvil-data"

export IRIS_UPLINK_URL := uplink_url

# List the available recipes (the default recipe).
list:
    @just --list

# Prepare a fresh checkout or worktree. Safe to rerun.
setup:
    #!/usr/bin/env bash
    set -euo pipefail
    [ -e CLAUDE.md ] || [ -L CLAUDE.md ] || ln -s AGENTS.md CLAUDE.md
    exclude="$(git rev-parse --git-path info/exclude)"
    # CLAUDE.md is a local symlink. .leftovers-local is an optional untracked
    # file of extra patterns for tools/leftovers.py. Neither may be committed.
    for line in CLAUDE.md .leftovers-local; do
        if grep -qxF "$line" "$exclude" 2>/dev/null; then
            echo "setup: $line is already in $exclude"
        elif { mkdir -p "$(dirname "$exclude")" && printf '%s\n' "$line" >> "$exclude"; } 2>/dev/null; then
            echo "setup: added $line to $exclude"
        else
            echo "setup: could not write $exclude. On the host, run:"
            echo "       echo $line >> $exclude"
        fi
    done
    hook="$(git rev-parse --git-path hooks/pre-commit)"
    if grep -qs pre-commit "$hook"; then
        echo "setup: pre-commit hook already installed"
    elif ! pre-commit install 2>/dev/null; then
        echo "setup: could not install the pre-commit hook here. On the host, run: pre-commit install"
    fi
    uv sync --quiet
    if uv run --quiet python -c 'import playwright.sync_api as a; p = a.sync_playwright().start(); p.chromium.launch().close(); p.stop()' 2>/dev/null; then
        echo "setup: Playwright chromium is installed"
    elif ! uv run playwright install chromium; then
        echo "setup: could not install chromium here. On the host, run: uv run playwright install chromium"
    fi

# Fetch the dependency apps named in anvil.yaml from GitHub at their pinned tags. No Anvil login.
deps:
    uv run --script tools/anvil_deps.py

# Lint (see .ruff.toml).
lint:
    ruff check .

# Format.
format:
    ruff format .

# Type-check with anvil-pyright.
check: deps
    anvil-pyright .

# Why there is no stubs step.
stubs:
    @echo "Nothing to do: anvil-pyright bundles the Anvil stubs. Do not wire in a .stubs/ directory (it switches the Anvil rules off)."

# Validate the Anvil manifest, forms and code. Nothing is staged in the repo tree outside the ignored .anvil/, so the target is the whole tree.
validate: deps
    anvil validate .

# Fail if anything left over from the project template has come back.
leftovers:
    python3 tools/leftovers.py

# Comment-to-code density, as a prompt to re-read, not a gate.
density:
    @python3 "{{ vault }}/technologies/python/tools/comment_ratio.py" client_code server_code

# The whole static gate. Run before every commit.
verify: lint check validate leftovers

# Hermetic unit tests. No stack needed.
unit:
    uv run pytest tests/unit

# [host] Build the app-server image (fetches the deps, stages a build context).
build: deps (_need-podman "build")
    rm -rf .anvil/build && mkdir -p .anvil/build/deps
    cp -R .anvil/src/. .anvil/build/deps/
    cp Containerfile .anvil/build/Containerfile
    cp server_code/requirements.txt .anvil/build/requirements.txt
    podman build -t {{ img }} .anvil/build
    rm -rf .anvil/build

# [host] Start the stack on :3030, or resume the stopped one (the DB survives).
up: (_need-podman "up")
    #!/usr/bin/env bash
    set -euo pipefail
    if podman container exists {{ ctr }}; then
        podman start {{ ctr }}
    else
        # Loopback only: the dev uplink key must not be reachable from the network.
        # The --dep-id flags come from anvil.yaml, so ids are never typed twice.
        # After a dep_id change in anvil.yaml, run `just fresh`.
        podman run -d --name {{ ctr }} -p 127.0.0.1:3030:3030 \
            -v "{{ justfile_directory() }}:/srv/{{ package }}:ro,z" -v {{ vol }}:/data \
            {{ img }} $(uv run --script tools/anvil_deps.py --dep-id-args)
    fi

# [host] Stop the stack.
down: (_need-podman "down")
    -podman stop {{ ctr }}

# [host] Stop and start the stack.
restart: down up

# [host] Throw away the container and its database, then start clean.
fresh: (_need-podman "fresh")
    -podman rm -f {{ ctr }}
    -podman volume rm {{ vol }}
    just up

# [host] Follow the stack's log.
logs: (_need-podman "logs")
    podman logs -f {{ ctr }}

# Seed the running stack over the dev uplink (needs the stack up).
seed: _need-stack
    uv run --script tools/dev_seed.py

# Browser tests against the running stack (needs the stack up).
e2e: _need-stack
    uv run pytest tests/e2e --base-url {{ base_url }}

[private]
_need-podman recipe:
    @podman info >/dev/null 2>&1 || { echo "just {{ recipe }} needs rootless podman, which can't run in this sandbox. Run 'just {{ recipe }}' from your own shell or a host session."; exit 1; }

[private]
_need-stack:
    @curl -fsS -o /dev/null --max-time 5 --retry {{ stack_retries }} --retry-delay 2 --retry-connrefused "{{ base_url }}" || { echo "No stack answering at {{ base_url }}. Start it on the host with 'just up'."; exit 1; }
