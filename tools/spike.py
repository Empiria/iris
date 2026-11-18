#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0", "anvil-uplink>=0.7.1", "playwright==1.65.2"]
# ///
"""Run a Phase 2 spike against a throwaway copy of the app.

A spike answers one question by running it. Each lives in tools/spikes/<name>/
with a probe.py and, for the stack spikes, an overlay: an app/ tree laid over a
copy of the app, and an optional anvil.patch.yaml merged into its anvil.yaml.
A spike with VARIANTS also has variants/<variant>/ trees laid on top of that.

The copy goes in the git-ignored .anvil/spikes/<name>/ and runs in a throwaway
container on a loopback port with a fresh database, so the product tree and the
stack are never touched. Host-only: it needs rootless podman and the
iris-anvil-dev image from `just build`.

    uv run --script tools/spike.py list
    uv run --script tools/spike.py all
    uv run --script tools/spike.py route_runtime
    uv run --script tools/spike.py iframe_matrix --assemble-only
"""

import argparse
import importlib.util
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import yaml

IMAGE = "iris-anvil-dev"
APP_ITEMS = (
    "anvil.yaml",
    "client_code",
    "server_code",
    "scripts",
    "theme",
    "requirements.txt",
)
READY_TRIES = 60
READY_PAUSE_S = 2


def merge_config(base, patch):
    """Merge a patch in: dicts recursively, lists joined, scalars replaced."""
    if isinstance(base, dict) and isinstance(patch, dict):
        merged = dict(base)
        for key, value in patch.items():
            merged[key] = merge_config(base[key], value) if key in base else value
        return merged
    if isinstance(base, list) and isinstance(patch, list):
        return list(base) + list(patch)
    return patch


def _check_dest(repo: Path, dest: Path) -> Path:
    spikes = (repo / ".anvil" / "spikes").resolve()
    resolved = dest.resolve()
    if spikes not in resolved.parents:
        raise ValueError(f"refusing to assemble into {dest}: not under {spikes}")
    return resolved


def _lay(tree: Path, dest: Path) -> None:
    if tree.is_dir():
        shutil.copytree(tree, dest, dirs_exist_ok=True)


def _patch(patch: Path, dest: Path) -> None:
    if not patch.is_file():
        return
    target = dest / "anvil.yaml"
    merged = merge_config(
        yaml.safe_load(target.read_text()) or {},
        yaml.safe_load(patch.read_text()) or {},
    )
    target.write_text(yaml.safe_dump(merged, sort_keys=True))


def assemble(repo: Path, overlay: Path, dest: Path, variant=None) -> Path:
    """Copy the app into dest, then lay the overlay (and a variant) over it."""
    dest = _check_dest(repo, dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for item in APP_ITEMS:
        src = repo / item
        if src.is_dir():
            shutil.copytree(src, dest / item, ignore=ignore)
        elif src.is_file():
            shutil.copy2(src, dest / item)
    roots = [overlay]
    if variant:
        roots.append(overlay / "variants" / variant)
    for root in roots:
        _lay(root / "app", dest)
        _patch(root / "anvil.patch.yaml", dest)
    return dest


def package_name(dest: Path) -> str:
    name = (yaml.safe_load((dest / "anvil.yaml").read_text()) or {}).get("package_name")
    if not name:
        raise ValueError(f"no package_name in {dest / 'anvil.yaml'}")
    return str(name)


def container_command(
    name, dest, port, package, dep_args, env=None, server_args=None
) -> list:
    """The podman run command. env goes to the container as -e, server_args to
    anvil-app-server after the standard flags (a spike's own settings)."""
    env_args = []
    for key, value in (env or {}).items():
        env_args += ["-e", f"{key}={value}"]
    return [
        "podman",
        "run",
        "-d",
        "--rm",
        "--name",
        name,
        *env_args,
        "-p",
        f"127.0.0.1:{port}:3030",
        "-v",
        f"{dest}:/srv/{package}:ro,z",
        "-v",
        "/data",
        IMAGE,
        "--app",
        f"/srv/{package}",
        # The page tells the browser where the app lives. Left alone that is the
        # container's own port, 3030, so a browser on the published port would
        # send its websocket and fetches to the wrong place.
        "--origin",
        f"http://localhost:{port}",
        "--port",
        "3030",
        *dep_args,
        *(server_args or []),
    ]


def spike_container(repo: Path, env) -> str:
    explicit = env.get("IRIS_SPIKE_CONTAINER")
    if explicit:
        return explicit
    stack = env.get("IRIS_CONTAINER") or f"iris-anvil-{Path(repo).name}"
    return f"{stack}-spike"


def spike_port(env=None) -> int:
    """A free loopback port for this run. No port is fixed: stacks from several
    checkouts and projects run side by side. The page needs the published port
    in its --origin, so the port is chosen here rather than left to podman."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def format_row(spike_id, verdict, evidence) -> str:
    text = " ".join(str(evidence).split()).replace("|", "\\|")
    return f"| {spike_id} | {verdict} | {text} |"


def discover(spikes_dir: Path) -> list:
    if not spikes_dir.is_dir():
        return []
    return sorted(
        p.name
        for p in spikes_dir.iterdir()
        if p.is_dir() and (p / "probe.py").is_file()
    )


def load_probe(overlay: Path):
    spikes = str(overlay.parent)
    if spikes not in sys.path:
        sys.path.insert(0, spikes)
    spec = importlib.util.spec_from_file_location(
        f"spike_probe_{overlay.name}", overlay / "probe.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _podman(*args, check=False):
    return subprocess.run(
        ["podman", *args], capture_output=True, text=True, check=check
    )


def _image_exists() -> bool:
    return _podman("image", "exists", IMAGE).returncode == 0


def _dep_args(repo: Path) -> list:
    out = subprocess.run(
        [
            "uv",
            "run",
            "--script",
            str(repo / "tools" / "anvil_deps.py"),
            "--root",
            str(repo),
            "--dep-id-args",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=repo,
    )
    return out.stdout.split()


def _wait_ready(port: int) -> bool:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = f"http://localhost:{port}/"
    for _ in range(READY_TRIES):
        try:
            with opener.open(url, timeout=5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(READY_PAUSE_S)
    return False


def _save_log(repo: Path, name: str, variant, container: str) -> None:
    logs = _podman("logs", container)
    suffix = f"-{variant}" if variant else ""
    target = repo / ".anvil" / "spikes" / f"{name}{suffix}.log"
    target.write_text((logs.stdout or "") + (logs.stderr or ""))


def _run_one(repo, name, variant, assemble_only, with_stack, env) -> list:
    overlay = repo / "tools" / "spikes" / name
    dest = repo / ".anvil" / "spikes" / name
    assemble(repo, overlay, dest, variant)
    if assemble_only:
        print(dest)
        return []
    probe = load_probe(overlay)
    if not (probe.NEEDS_STACK or with_stack):
        return list(probe.run(""))
    container = spike_container(repo, env)
    port = spike_port(env)
    _podman("rm", "-f", "--time", "0", container)
    options = getattr(probe, "container_options", None)
    env_vars, server_args = options(variant) if options else ({}, [])
    cmd = container_command(
        container,
        dest,
        port,
        package_name(dest),
        _dep_args(repo),
        env=env_vars,
        server_args=server_args,
    )
    started = _podman(*cmd[1:])
    if started.returncode != 0:
        return [(name, "FAIL", f"podman run failed: {started.stderr.strip()[:300]}")]
    try:
        if not _wait_ready(port):
            return [(name, "FAIL", f"no 200 from localhost:{port} after boot wait")]
        base = f"http://localhost:{port}/"
        # A probe that needs the container's log asks for it by this name.
        os.environ["IRIS_SPIKE_ACTIVE_CONTAINER"] = container
        if variant:
            return list(probe.run(base, variant))
        return list(probe.run(base))
    finally:
        _save_log(repo, name, variant, container)
        _podman("rm", "-f", "--time", "0", container)


def run_spike(repo, name, assemble_only, with_stack, env) -> list:
    """Run one spike (once per variant when its probe declares VARIANTS)."""
    probe = load_probe(repo / "tools" / "spikes" / name)
    variants = list(getattr(probe, "VARIANTS", []) or [None])
    rows = []
    for variant in variants:
        rows += _run_variant(repo, name, variant, assemble_only, with_stack, env)
    return rows


def _run_variant(repo, name, variant, assemble_only, with_stack, env) -> list:
    try:
        return _run_one(repo, name, variant, assemble_only, with_stack, env)
    except Exception as exc:
        return [(name, "FAIL", f"runner error {type(exc).__name__}: {exc}")]


def _order(repo: Path, names: list) -> list:
    """Stack spikes first, in name order, then the ones that need no stack."""
    stack, other = [], []
    for name in names:
        probe = load_probe(repo / "tools" / "spikes" / name)
        (stack if probe.NEEDS_STACK else other).append(name)
    return stack + other


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("name", help="a spike name, 'all' or 'list'")
    parser.add_argument("--assemble-only", action="store_true")
    parser.add_argument(
        "--with-stack",
        action="store_true",
        help="start the container even for a spike that does not need one",
    )
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    names = discover(repo / "tools" / "spikes")
    if args.name == "list":
        print("\n".join(names))
        return 0
    if args.name != "all" and args.name not in names:
        print(
            f"spike: no spike {args.name!r}; known: {', '.join(names)}", file=sys.stderr
        )
        return 2
    chosen = _order(repo, names) if args.name == "all" else [args.name]
    needs_podman = not args.assemble_only
    if needs_podman and not _image_exists():
        print(
            f"spike: image {IMAGE} not found; run 'just build' on the host first",
            file=sys.stderr,
        )
        return 1
    results = repo / ".anvil" / "spike-results.md"
    results.parent.mkdir(parents=True, exist_ok=True)
    for name in chosen:
        print(f"== spike {name}")
        for spike_id, verdict, evidence in run_spike(
            repo, name, args.assemble_only, args.with_stack, os.environ
        ):
            row = format_row(spike_id, verdict, evidence)
            print(row, flush=True)
            with results.open("a") as out:
                out.write(row + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
