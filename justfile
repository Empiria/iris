# Iris justfile. `just verify` is the static gate; `just unit` and `just e2e` are the tests.
#
# Sandbox rule: recipes marked [host] need rootless podman, which can't run in a
# worker sandbox. They fail fast there and name the command to run on the host.

vault := env_var_or_default("MNEMOSYNE_VAULT", env_var("HOME") + "/projects/empiria/mnemosyne")

base_url := env_var_or_default("IRIS_URL", "http://localhost:3030/")
uplink_url := env_var_or_default("IRIS_UPLINK_URL", "ws://localhost:3030/_/uplink")

# How many times the stack guard retries (2 s apart) before it gives up.
stack_retries := env_var_or_default("IRIS_STACK_RETRIES", "30")

# How long host-check waits for a booting stack to answer 200, in seconds.
boot_timeout := env_var_or_default("IRIS_BOOT_TIMEOUT", "600")

# The app's package_name, read from anvil.yaml so an IDE rename needs no edit
# here. The app is mounted at /srv/<package>.
package := `sed -n 's/^package_name: *//p' anvil.yaml`
img := "iris-anvil-dev"
# One container and database per checkout, named after its directory, so a
# stale container left by another checkout or worktree can't block this one.
# IRIS_CONTAINER overrides the name. Only one stack can hold port 3030 at a time.
ctr := env_var_or_default("IRIS_CONTAINER", "iris-anvil-" + file_name(justfile_directory()))
vol := ctr + "-data"

# The spike container: a second, throwaway container beside the stack, named from
# the checkout so two checkouts never share one fixed name.
spike_ctr := env_var_or_default("IRIS_SPIKE_CONTAINER", ctr + "-spike")

export IRIS_UPLINK_URL := uplink_url
export IRIS_SPIKE_CONTAINER := spike_ctr

# Playwright browsers live in the repo's git-ignored .anvil/, not under $HOME, so
# every recipe and check finds them whatever HOME is. `just setup` fills it.
export PLAYWRIGHT_BROWSERS_PATH := env_var_or_default("PLAYWRIGHT_BROWSERS_PATH", justfile_directory() + "/.anvil/ms-playwright")

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
    # Build the hook environments now, so a commit made without network access can still run them.
    if grep -qs pre-commit "$hook" && ! hook_err="$(pre-commit install-hooks 2>&1)"; then
        printf '%s\n' "$hook_err" | tail -n 3
        echo "setup: could not build the pre-commit hook environments here. On the host, run: pre-commit install-hooks"
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

# Validate the Anvil manifest, forms and code. Each app path is named, not "." as a whole, because tools/spikes/ holds overlay forms that are only valid once laid into a spike copy of the app.
validate: deps
    anvil validate anvil.yaml
    anvil validate client_code
    anvil validate server_code
    anvil validate theme

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
        # After a package_name or dep_id change in anvil.yaml, run `just fresh`.
        [ -n "{{ package }}" ] || { echo "up: no package_name in anvil.yaml"; exit 1; }
        podman run -d --name {{ ctr }} -p 127.0.0.1:3030:3030 \
            -v "{{ justfile_directory() }}:/srv/{{ package }}:ro,z" -v {{ vol }}:/data \
            {{ img }} --app /srv/{{ package }} $(uv run --script tools/anvil_deps.py --dep-id-args)
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

# [host] Force-remove the stack's container, even one that won't stop. Fails if it is still there.
stack-reset: (_need-podman "stack-reset")
    #!/usr/bin/env bash
    set -uo pipefail
    podman container exists {{ ctr }} || { echo "stack-reset: no container {{ ctr }}"; exit 0; }
    podman rm -f --time 0 {{ ctr }} && exit 0
    echo "stack-reset: rm failed, cleaning up {{ ctr }} and retrying"
    podman container cleanup {{ ctr }} || true
    podman rm -f --time 0 {{ ctr }} && exit 0
    echo "stack-reset: {{ ctr }} is wedged and could not be removed"
    exit 1

# [host] Follow the stack's log.
logs: (_need-podman "logs")
    podman logs -f {{ ctr }}

# [host] Seed the running stack over the dev uplink (needs the stack up).
# Host-only: a worker sandbox can't reach the host stack (see AGENTS.md).
seed: _need-stack
    uv run --script tools/dev_seed.py

# [host] Browser tests against the running stack (needs the stack up).
# Host-only: a worker sandbox can't reach the host stack (see AGENTS.md).
e2e: _need-stack
    uv run pytest tests/e2e --base-url {{ base_url }}

# [host] Run a Phase 2 spike: `just spike all`, `just spike <name>` or `just spike list`.
# Host-only like the other stack recipes: it needs podman and the image from `just build`.
spike *args: (_need-podman "spike")
    uv run --script tools/spike.py {{ args }}

# [host] Force-remove the spike container. Fine if there isn't one.
# Host-only like the other stack recipes.
spike-down: (_need-podman "spike-down")
    -podman rm -f --time 0 {{ spike_ctr }}

# [host] Run every host-only check in order, stop at the first failure, log to .anvil/host-check.txt, leave the stack up.
host-check: (_need-podman "host-check")
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p .anvil
    out="$PWD/.anvil/host-check.txt"
    : > "$out"
    exec > >(tee -a "$out") 2>&1
    step=0
    name="start"
    begin() { step=$((step + 1)); name="$1"; echo; echo "== step $step: $name"; }
    fail() { echo "host-check: $*" >&2; exit 1; }
    trap 'rc=$?; [ "$rc" -eq 0 ] || { echo; echo "host-check: FAILED at step $step ($name), exit $rc. Log: $out"; }' EXIT
    # Prints the seconds until the stack answers 200.
    wait_200() {
        local start=$SECONDS
        until [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 '{{ base_url }}' || true)" = 200 ]; do
            [ $((SECONDS - start)) -lt {{ boot_timeout }} ] || fail "no 200 from {{ base_url }} after {{ boot_timeout }} s"
            sleep 3
        done
        echo $((SECONDS - start))
    }
    echo "host-check: $(date -Is) at $(git rev-parse --short HEAD) on $(git branch --show-current)"

    begin "podman"
    podman_version="$(podman --version)"
    echo "$podman_version"

    begin "this checkout's container ({{ ctr }}) is not wedged"
    just stack-reset

    begin "setup: CLAUDE.md link, exclude entries, pre-commit hook, Playwright chromium"
    gitconfig="$(git rev-parse --git-common-dir)/config"
    config_before="$(md5sum < "$gitconfig")"
    just setup
    exclude="$(git rev-parse --git-path info/exclude)"
    for line in CLAUDE.md .leftovers-local; do
        grep -qxF "$line" "$exclude" || fail "$line is not in $exclude"
    done
    [ "$(readlink CLAUDE.md)" = AGENTS.md ] || fail "CLAUDE.md is not a link to AGENTS.md"
    git check-ignore -q CLAUDE.md || fail "git does not ignore CLAUDE.md"
    grep -qs pre-commit "$(git rev-parse --git-path hooks/pre-commit)" || fail "the pre-commit hook is not installed"
    uv run --quiet python -c 'import playwright.sync_api as a; p = a.sync_playwright().start(); p.chromium.launch().close(); p.stop()' \
        || fail "Playwright chromium does not launch"
    echo "setup checks passed"

    begin "dependencies from GitHub with no Anvil login"
    marker="$(mktemp)"
    rm -rf .anvil/deps .anvil/src
    just deps
    [ "$(md5sum < "$gitconfig")" = "$config_before" ] || fail "$gitconfig changed"
    if [ -d "$HOME/.config/anvil-cli" ] && [ -n "$(find "$HOME/.config/anvil-cli" -newer "$marker" -print -quit)" ]; then
        fail "something wrote to ~/.config/anvil-cli"
    fi
    rm -f "$marker"
    echo "shared git config unchanged, no anvil-cli login state written"

    begin "build the image (A2)"
    t0=$SECONDS
    just build
    build_secs=$((SECONDS - t0))
    podman image exists {{ img }} || fail "image {{ img }} is missing"
    echo "just build took ${build_secs} s"

    begin "the runtime user finds the app-server JAR without a download (A3)"
    # The library prints its own "Found ..." or "Downloading ..." line before the path we print.
    jar_out="$(podman run --rm --entrypoint python3 {{ img }} -c 'import anvil_app_server as a; print(a.find_or_download_app_server())' 2>&1)"
    echo "$jar_out"
    if printf '%s\n' "$jar_out" | grep -qi 'download'; then fail "the runtime user had to download the JAR"; fi
    jar="$(printf '%s\n' "$jar_out" | tail -n 1)"
    case "$jar" in *.jar) ;; *) fail "expected the last line to be a path ending in .jar" ;; esac

    begin "cold boot on a clean database (A7)"
    just fresh
    boot_secs="$(wait_200)"
    echo "first 200 after ${boot_secs} s"

    begin "the port is published on loopback only"
    port="$(podman port {{ ctr }})"
    echo "$port"
    [ "$port" = "3030/tcp -> 127.0.0.1:3030" ] || fail "expected 3030/tcp -> 127.0.0.1:3030"
    listen="$(ss -ltnH 'sport = :3030')"
    echo "$listen"
    if grep -qE '(0\.0\.0\.0|\[::\]|\*):3030' <<<"$listen"; then fail "port 3030 listens beyond loopback"; fi

    begin "the server got the app path and dependency ids from anvil.yaml"
    cmd="$(podman inspect {{ ctr }} --format '{{{{json .Config.Cmd}}')"
    echo "$cmd"
    grep -qF '"--app","/srv/{{ package }}"' <<<"$cmd" || fail "the server command lacks --app /srv/{{ package }}"
    dep_args="$(uv run --script tools/anvil_deps.py --dep-id-args)"
    [ -n "$dep_args" ] || fail "anvil_deps.py --dep-id-args printed nothing"
    for arg in $dep_args; do
        [ "$arg" = --dep-id ] && continue
        grep -qF "\"$arg\"" <<<"$cmd" || fail "the server command lacks $arg"
    done

    begin "the server log has no import errors"
    if podman logs {{ ctr }} 2>&1 | grep -iE 'traceback|cannot find dependenc|modulenotfound'; then
        fail "errors in the server log (above)"
    fi

    begin "seed over the dev uplink, twice (QA-05)"
    just seed
    just seed

    begin "browser test (QA-06, A4)"
    just e2e

    begin "the server log has no client error reports"
    if podman logs {{ ctr }} 2>&1 | grep -A3 'Error report from client code'; then
        fail "the browser reported a client error (above)"
    fi

    begin "lifecycle: down"
    just down
    if podman ps --format '{{{{.Names}}' | grep -qx {{ ctr }}; then fail "{{ ctr }} is still running"; fi
    if curl -fsS -o /dev/null --max-time 3 '{{ base_url }}' 2>/dev/null; then fail "{{ base_url }} still answers"; fi
    echo "stopped"

    begin "lifecycle: up"
    just up
    secs="$(wait_200)"
    echo "200 after ${secs} s"

    begin "lifecycle: restart"
    just restart
    secs="$(wait_200)"
    echo "200 after ${secs} s"

    begin "lifecycle: logs"
    rc=0
    timeout -k 2 5 just logs > /dev/null || rc=$?
    [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ] || fail "just logs exited $rc instead of following"
    echo "just logs follows the log"

    begin "lifecycle: fresh, then seed and e2e again"
    just fresh
    podman volume exists {{ vol }} || fail "volume {{ vol }} is missing"
    secs="$(wait_200)"
    echo "200 after ${secs} s"
    just seed
    just e2e

    echo
    echo "== summary"
    echo "podman: $podman_version"
    echo "just build: ${build_secs} s"
    echo "cold boot to first 200: ${boot_secs} s"
    echo "seed and e2e output: in the seed, browser test and fresh steps above"
    echo "host-check: all steps passed. The stack is still running at {{ base_url }}."

[private]
_need-podman recipe:
    @podman info >/dev/null 2>&1 || { echo "just {{ recipe }} needs rootless podman, which can't run in this sandbox. Run 'just {{ recipe }}' from your own shell or a host session."; exit 1; }

[private]
_need-stack:
    @curl -fsS -o /dev/null --max-time 5 --retry {{ stack_retries }} --retry-delay 2 --retry-connrefused "{{ base_url }}" || { echo "No stack answering at {{ base_url }}. Start it on the host with 'just up'. A worker sandbox can't reach the host stack (see AGENTS.md), so run this recipe on the host."; exit 1; }
