"""Contract tests for tools/spike.py, the Phase 2 spike runner.

Only the runner's pure parts are tested here: the config merge, the app copy,
the container command, the names and the result rows. Starting a container and
running a probe needs the host stack, so those are left to `just spike`.

The Phase 3 probes (crypto_derive, vdo_hash) get the same treatment: their pure
helpers (the reference derivation, the vdo.ninja hash, the URL builders and the
result-line checks) are tested here, and the browser parts are left to the probes.
"""

import ast
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def spike(load_tool):
    return load_tool("spike")


def write(path: Path, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def repo(tmp_path):
    """A small fake checkout: the app files plus things that must not be copied."""
    root = tmp_path / "iris-checkout"
    write(root / "anvil.yaml", "package_name: iris\nservices: []\n")
    write(root / "client_code" / "startup.py", "client")
    write(root / "client_code" / "__pycache__" / "junk.pyc", "junk")
    write(root / "server_code" / "health.py", "server")
    write(root / "server_code" / "requirements.txt", "pkg")
    write(root / "theme" / "parameters.yaml", "theme")
    write(root / "requirements.txt", "top")
    write(root / ".git" / "HEAD", "ref")
    write(root / ".anvil" / "deps" / "x", "dep")
    write(root / "tests" / "t.py", "test")
    write(root / "tools" / "t.py", "tool")
    return root


@pytest.fixture
def dest(repo):
    return repo / ".anvil" / "spikes" / "demo"


class TestMergeConfig:
    def test_dicts_merge_recursively(self, spike):
        base = {"a": {"b": 1, "c": 2}, "d": 3}
        patch = {"a": {"c": 9, "e": 4}}
        assert spike.merge_config(base, patch) == {
            "a": {"b": 1, "c": 9, "e": 4},
            "d": 3,
        }

    def test_lists_are_concatenated(self, spike):
        assert spike.merge_config({"x": [1, 2]}, {"x": [3]}) == {"x": [1, 2, 3]}

    def test_scalars_are_replaced(self, spike):
        assert spike.merge_config({"x": 1}, {"x": 2}) == {"x": 2}

    def test_a_type_change_replaces(self, spike):
        assert spike.merge_config({"x": [1]}, {"x": "s"}) == {"x": "s"}

    def test_inputs_are_not_mutated(self, spike):
        base = {"a": {"b": [1]}}
        patch = {"a": {"b": [2]}}
        spike.merge_config(base, patch)
        assert base == {"a": {"b": [1]}}
        assert patch == {"a": {"b": [2]}}


class TestAssemble:
    def test_copies_only_the_app_files(self, spike, repo, dest):
        overlay = repo / "tools" / "spikes" / "demo"
        spike.assemble(repo, overlay, dest)
        copied = sorted(p.name for p in dest.iterdir())
        assert copied == [
            "anvil.yaml",
            "client_code",
            "requirements.txt",
            "server_code",
            "theme",
        ]

    def test_scripts_are_copied_when_the_app_has_them(self, spike, repo, dest):
        write(repo / "scripts" / "CreateStaff.py", "script")
        spike.assemble(repo, repo / "tools" / "spikes" / "demo", dest)
        assert (dest / "scripts" / "CreateStaff.py").read_text() == "script"

    def test_no_bytecode_is_copied(self, spike, repo, dest):
        spike.assemble(repo, repo / "tools" / "spikes" / "demo", dest)
        assert not list(dest.rglob("*.pyc"))

    def test_requirements_are_optional(self, spike, repo, dest):
        (repo / "requirements.txt").unlink()
        spike.assemble(repo, repo / "tools" / "spikes" / "demo", dest)
        assert not (dest / "requirements.txt").exists()

    def test_overlay_files_replace_and_add(self, spike, repo, dest):
        overlay = repo / "tools" / "spikes" / "demo"
        write(overlay / "app" / "client_code" / "startup.py", "overlaid")
        write(overlay / "app" / "server_code" / "new.py", "new")
        spike.assemble(repo, overlay, dest)
        assert (dest / "client_code" / "startup.py").read_text() == "overlaid"
        assert (dest / "server_code" / "new.py").read_text() == "new"
        assert (dest / "server_code" / "health.py").read_text() == "server"

    def test_the_repo_is_left_alone(self, spike, repo, dest):
        overlay = repo / "tools" / "spikes" / "demo"
        write(overlay / "app" / "client_code" / "startup.py", "overlaid")
        spike.assemble(repo, overlay, dest)
        assert (repo / "client_code" / "startup.py").read_text() == "client"

    def test_patch_is_merged_into_anvil_yaml(self, spike, repo, dest):
        overlay = repo / "tools" / "spikes" / "demo"
        write(overlay / "anvil.patch.yaml", "services:\n- source: s\nname: Demo\n")
        spike.assemble(repo, overlay, dest)
        merged = yaml.safe_load((dest / "anvil.yaml").read_text())
        assert merged == {
            "package_name": "iris",
            "services": [{"source": "s"}],
            "name": "Demo",
        }

    def test_a_variant_is_laid_over_the_overlay(self, spike, repo, dest):
        overlay = repo / "tools" / "spikes" / "demo"
        write(overlay / "app" / "client_code" / "startup.py", "overlaid")
        write(overlay / "variants" / "one" / "app" / "client_code" / "startup.py", "v1")
        write(overlay / "variants" / "one" / "app" / "client_code" / "extra.py", "e")
        write(overlay / "variants" / "two" / "anvil.patch.yaml", "name: Two\n")
        spike.assemble(repo, overlay, dest, "one")
        assert (dest / "client_code" / "startup.py").read_text() == "v1"
        assert (dest / "client_code" / "extra.py").exists()
        assert "name" not in yaml.safe_load((dest / "anvil.yaml").read_text())

    def test_a_variant_patch_is_merged_after_the_overlay_patch(self, spike, repo, dest):
        overlay = repo / "tools" / "spikes" / "demo"
        write(overlay / "anvil.patch.yaml", "name: Base\nextra: 1\n")
        write(overlay / "variants" / "two" / "anvil.patch.yaml", "name: Two\n")
        spike.assemble(repo, overlay, dest, "two")
        merged = yaml.safe_load((dest / "anvil.yaml").read_text())
        assert merged["name"] == "Two"
        assert merged["extra"] == 1

    def test_a_variant_that_does_not_exist_adds_nothing(self, spike, repo, dest):
        overlay = repo / "tools" / "spikes" / "demo"
        write(overlay / "app" / "server_code" / "new.py", "new")
        spike.assemble(repo, overlay, dest, "control")
        assert (dest / "server_code" / "new.py").read_text() == "new"

    def test_a_second_assemble_starts_clean(self, spike, repo, dest):
        overlay = repo / "tools" / "spikes" / "demo"
        spike.assemble(repo, overlay, dest)
        write(dest / "server_code" / "stale.py", "stale")
        spike.assemble(repo, overlay, dest)
        assert not (dest / "server_code" / "stale.py").exists()

    @pytest.mark.parametrize(
        "where",
        [".", "client_code", ".anvil", ".anvil/spikes", ".anvil/other/demo", "../x"],
    )
    def test_refuses_a_dest_outside_the_spikes_directory(self, spike, repo, where):
        overlay = repo / "tools" / "spikes" / "demo"
        with pytest.raises(ValueError):
            spike.assemble(repo, overlay, repo / where)
        assert (repo / "client_code" / "startup.py").read_text() == "client"

    def test_refuses_a_dest_that_escapes_through_dotdot(self, spike, repo):
        sneaky = repo / ".anvil" / "spikes" / ".." / ".." / "client_code"
        with pytest.raises(ValueError):
            spike.assemble(repo, repo / "tools" / "spikes" / "demo", sneaky)
        assert (repo / "client_code" / "startup.py").read_text() == "client"


class TestContainerCommand:
    def command(self, spike, dest, **over):
        args = {
            "name": "iris-anvil-co-spike",
            "dest": dest,
            "port": 41031,
            "package": "iris",
            "dep_args": ["--dep-id", "dep_a=routing"],
        }
        args.update(over)
        return spike.container_command(**args)

    def test_publishes_loopback_only(self, spike, dest):
        cmd = self.command(spike, dest)
        assert "127.0.0.1:41031:3030" in cmd
        assert not any(a.startswith("41031") for a in cmd)

    def test_the_origin_is_the_published_port_and_the_app_still_listens_on_3030(
        self, spike, dest
    ):
        cmd = self.command(spike, dest, port=4000)
        assert cmd[cmd.index("--origin") + 1] == "http://localhost:4000"
        assert cmd[cmd.index("--port") + 1] == "3030"

    def test_the_port_is_a_parameter(self, spike, dest):
        assert "127.0.0.1:4000:3030" in self.command(spike, dest, port=4000)

    def test_is_throwaway_and_named(self, spike, dest):
        cmd = self.command(spike, dest)
        assert cmd[:2] == ["podman", "run"]
        assert "--rm" in cmd
        assert cmd[cmd.index("--name") + 1] == "iris-anvil-co-spike"

    def test_mounts_the_app_read_only_with_the_z_label(self, spike, dest):
        cmd = self.command(spike, dest)
        assert f"{dest}:/srv/iris:ro,z" in cmd

    def test_data_is_an_anonymous_volume(self, spike, dest):
        cmd = self.command(spike, dest)
        assert "/data" in cmd
        assert "-v" in cmd
        mounts = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-v"]
        assert "/data" in mounts

    def test_image_then_app_then_dep_args(self, spike, dest):
        cmd = self.command(spike, dest)
        i = cmd.index("iris-anvil-dev")
        assert cmd[i:] == [
            "iris-anvil-dev",
            "--app",
            "/srv/iris",
            "--origin",
            "http://localhost:41031",
            "--port",
            "3030",
            "--dep-id",
            "dep_a=routing",
        ]

    def test_env_goes_before_the_image_as_dash_e(self, spike, dest):
        cmd = self.command(spike, dest, env={"IRIS_STAFF_PASSWORD": "x y"})
        i = cmd.index("-e")
        assert cmd[i + 1] == "IRIS_STAFF_PASSWORD=x y"
        assert i < cmd.index("iris-anvil-dev")

    def test_no_env_adds_no_dash_e(self, spike, dest):
        assert "-e" not in self.command(spike, dest)

    def test_server_args_go_last(self, spike, dest):
        cmd = self.command(spike, dest, server_args=["--secret", "a=b"])
        assert cmd[-2:] == ["--secret", "a=b"]
        assert cmd.index("--dep-id") < cmd.index("--secret")

    def test_package_drives_the_mount_and_app(self, spike, dest):
        cmd = self.command(spike, dest, package="other")
        assert f"{dest}:/srv/other:ro,z" in cmd
        assert cmd[cmd.index("--app") + 1] == "/srv/other"


class TestPackageName:
    def test_reads_it(self, spike, tmp_path):
        write(tmp_path / "anvil.yaml", "package_name: demo_pkg\nname: x\n")
        assert spike.package_name(tmp_path) == "demo_pkg"

    def test_raises_when_missing(self, spike, tmp_path):
        write(tmp_path / "anvil.yaml", "name: x\n")
        with pytest.raises(ValueError):
            spike.package_name(tmp_path)


class TestNames:
    def test_container_follows_the_checkout_directory(self, spike, tmp_path):
        assert spike.spike_container(tmp_path / "alpha", {}) == "iris-anvil-alpha-spike"

    def test_two_checkouts_get_different_names(self, spike, tmp_path):
        a = spike.spike_container(tmp_path / "alpha", {})
        b = spike.spike_container(tmp_path / "beta", {})
        assert a != b

    def test_stack_container_override_is_the_base(self, spike, tmp_path):
        env = {"IRIS_CONTAINER": "mine"}
        assert spike.spike_container(tmp_path / "alpha", env) == "mine-spike"

    def test_spike_container_override_wins(self, spike, tmp_path):
        env = {"IRIS_CONTAINER": "mine", "IRIS_SPIKE_CONTAINER": "exact"}
        assert spike.spike_container(tmp_path / "alpha", env) == "exact"

    def test_never_the_bare_stack_name(self, spike, tmp_path):
        repo = tmp_path / "alpha"
        assert spike.spike_container(repo, {}) != "iris-anvil-alpha"
        assert spike.spike_container(repo, {"IRIS_CONTAINER": "m"}) != "m"

    def test_port_is_a_free_loopback_port(self, spike):
        import socket

        port = spike.spike_port({})
        assert 1024 <= port <= 65535
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))

    def test_no_fixed_port(self, spike):
        assert not hasattr(spike, "DEFAULT_PORT")


class TestFormatRow:
    def test_one_table_row(self, spike):
        assert (
            spike.format_row("S1a", "PASS", "rendered") == "| S1a | PASS | rendered |"
        )

    def test_pipes_in_evidence_are_escaped(self, spike):
        row = spike.format_row("S1a", "FAIL", "a|b")
        assert row == "| S1a | FAIL | a\\|b |"

    def test_newlines_do_not_break_the_row(self, spike):
        assert "\n" not in spike.format_row("S1a", "FAIL", "a\nb")


class TestDiscover:
    def test_sorted_directories_with_a_probe(self, spike, tmp_path):
        write(tmp_path / "zeta" / "probe.py")
        write(tmp_path / "alpha" / "probe.py")
        write(tmp_path / "no_probe" / "app" / "x.py")
        write(tmp_path / "loose.py")
        assert spike.discover(tmp_path) == ["alpha", "zeta"]

    def test_a_missing_directory_is_empty(self, spike, tmp_path):
        assert spike.discover(tmp_path / "nope") == []


SPIKES = ROOT / "tools" / "spikes"
EXPECTED = {
    "vdo_fragment",
    "route_runtime",
    "route_own",
    "schema_users",
    "iframe_matrix",
    "staff_script",
    "crypto_derive",
    "vdo_hash",
}


def test_every_overlay_has_a_probe():
    dirs = {p.name for p in SPIKES.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert dirs == EXPECTED
    for name in dirs:
        probe = SPIKES / name / "probe.py"
        assert probe.exists(), name
        tree = ast.parse(probe.read_text())
        assigned = {
            t.id
            for node in tree.body
            if isinstance(node, ast.Assign)
            for t in node.targets
            if isinstance(t, ast.Name)
        }
        funcs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        assert "NEEDS_STACK" in assigned, name
        assert "run" in funcs, name


def _probe(spike, name):
    return spike.load_probe(SPIKES / name)


class TestVdoHashProbe:
    @pytest.fixture
    def probe(self, spike):
        return _probe(spike, "vdo_hash")

    def test_generate_hash_is_sha256_hex_cut_to_half_the_length_in_bytes(self, probe):
        # sha256("abc") = ba7816bf 8f01cfea 414140de ...
        assert probe.generate_hash("abc") == (
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )
        assert probe.generate_hash("abc", 16) == "ba7816bf8f01cfea"
        assert probe.generate_hash("abc", 6) == "ba7816"
        assert probe.generate_hash("abc", 4) == "ba78"

    def test_room_id_hashes_room_password_salt_and_token(self, probe):
        assert probe.room_id("r", "p", "s") == probe.generate_hash("rps", 16)
        assert probe.room_id("r", "p", "s", "t") == probe.generate_hash("rpst", 16)

    def test_the_salt_changes_the_room_id(self, probe):
        assert probe.room_id("r", "p", "vdo.ninja") != probe.room_id("r", "p", "x")

    def test_password_hash_is_the_start_of_the_six_character_hash(self, probe):
        full = probe.generate_hash("secretvdo.ninja", 6)
        assert probe.password_hash("secret", "vdo.ninja") == full[:4]
        assert probe.password_hash("secret", "vdo.ninja", 6) == full

    def test_a_random_room_is_prefixed_and_unique(self, probe):
        a, b = probe.random_room(), probe.random_room()
        assert a.startswith("irisspike")
        assert a[len("irisspike") :].isalpha()
        assert a != b

    def test_url_with_the_password_in_the_query(self, probe):
        url = probe.build_url("https://vdo.ninja/", "r1", "pw", join=False)
        assert url == "https://vdo.ninja/?room=r1&password=pw"

    def test_url_with_the_password_in_the_fragment(self, probe):
        url = probe.build_url(
            "https://vdo.ninja", "r1", "pw", password_in_fragment=True, join=False
        )
        assert url == "https://vdo.ninja/?room=r1#password=pw"

    def test_url_with_salt_and_hash(self, probe):
        url = probe.build_url("https://vdo.ninja", "r1", "pw", "s", "ab12", join=False)
        assert url == "https://vdo.ninja/?room=r1&password=pw&salt=s&hash=ab12"

    def test_a_joining_url_uses_the_fake_camera_params(self, probe):
        url = probe.build_url("https://vdo.ninja", "r1")
        assert url == "https://vdo.ninja/?room=r1&webcam&autostart&label=Spike"

    def test_a_password_is_percent_encoded(self, probe):
        url = probe.build_url("https://vdo.ninja", "r1", "a b&c", join=False)
        assert url.endswith("password=a%20b%26c")

    def test_room_ids_are_read_from_sent_frames(self, probe):
        frames = [
            '{"request":"joinroom","roomid":"0123456789abcdef"}',
            '{"roomid": "0123456789abcdef"}',
            '{"request":"ping"}',
            '{"roomid":"fedcba9876543210"}',
        ]
        assert probe.room_ids_in(frames) == ["0123456789abcdef", "fedcba9876543210"]

    def test_no_frames_means_no_room_ids(self, probe):
        assert probe.room_ids_in([]) == []

    def test_the_build_is_read_from_the_version_assignment(self, probe):
        assert probe.build_of('session.version = "31.1"; // note') == "31.1"
        assert probe.build_of("nothing here") is None

    def test_a_result_line_is_one_line(self, probe):
        assert probe.format_line("S2a", "PASS", "a\n  b") == "S2a PASS a b"

    def test_the_proxy_credentials_are_split_out(self, probe, monkeypatch):
        monkeypatch.setenv("HTTPS_PROXY", "http://user:pw@127.0.0.1:3128")
        assert probe._proxy() == {
            "server": "http://127.0.0.1:3128",
            "username": "user",
            "password": "pw",
        }

    def test_no_proxy_in_the_environment(self, probe, monkeypatch):
        monkeypatch.delenv("HTTPS_PROXY", raising=False)
        monkeypatch.delenv("HTTP_PROXY", raising=False)
        assert probe._proxy() is None

    def test_it_needs_no_stack(self, probe):
        assert probe.NEEDS_STACK is False


class TestCryptoDeriveProbe:
    @pytest.fixture
    def probe(self, spike):
        return _probe(spike, "crypto_derive")

    def test_the_reference_matches_the_rfc_7914_vector(self, probe):
        # RFC 7914 section 11: PBKDF2-HMAC-SHA-256, P="passwd", S="salt", c=1.
        # The first 32 bytes of its 64-byte output.
        assert probe.reference_hex("passwd", "salt", 1) == (
            "55ac046e56e3089fec1691c22544b605f94185216dde0465e68b9d57c20dacbc"
        )

    def test_the_fixed_inputs_have_a_pinned_reference(self, probe):
        assert probe.reference_hex() == (
            "9b1e78d56c5feb5a819a01cd18229723a6af007c036c3d4a8fbdf1479a52b482"
        )

    def test_it_needs_a_stack(self, probe):
        assert probe.NEEDS_STACK is True

    def test_fields_are_parsed_from_the_output_line(self, probe):
        fields = probe.parse_fields("S1a hex=ab12 ms100000=250 ms600000=1500 DONE")
        assert fields == {
            "case": "S1a",
            "hex": "ab12",
            "ms100000": "250",
            "ms600000": "1500",
        }

    def test_a_value_may_contain_an_equals_sign(self, probe):
        assert probe.parse_fields("S1b call_js=err:a=b")["call_js"] == "err:a=b"

    def test_timings_are_keyed_by_iterations(self, probe):
        fields = probe.parse_fields("S3 ms100000=40 ms300000=120 error=x")
        assert probe.timings(fields) == {100000: 40, 300000: 120}

    def test_s1a_passes_on_the_reference_hex_with_timings(self, probe):
        fields = {"hex": "aa", "ms100000": "5"}
        assert probe.check_s1a(fields, "aa")[0] == "PASS"

    def test_s1a_fails_on_a_wrong_hex(self, probe):
        fields = {"hex": "bb", "ms100000": "5"}
        assert probe.check_s1a(fields, "aa")[0] == "FAIL"

    def test_s1a_fails_with_no_hex(self, probe):
        verdict, evidence = probe.check_s1a({"hex_error": "TypeError"}, "aa")
        assert verdict == "FAIL"
        assert "TypeError" in evidence

    def test_s1b_names_which_route_worked(self, probe):
        fields = {"call_js": "err:x", "window": "ok", "hex": "aa", "via": "window"}
        verdict, evidence = probe.check_s1b(fields, "aa")
        assert verdict == "PASS"
        assert "['window']" in evidence

    def test_s1b_fails_when_neither_route_worked(self, probe):
        fields = {"call_js": "err:x", "window": "err:y"}
        assert probe.check_s1b(fields, "aa")[0] == "FAIL"

    def test_s1c_needs_every_result_to_match(self, probe):
        assert probe.check_s1c({"anvil_js": "aa", "call_js": "aa"}, "aa")[0] == "PASS"
        assert probe.check_s1c({"anvil_js": "aa", "call_js": "bb"}, "aa")[0] == "FAIL"

    def test_s1c_fails_with_no_result(self, probe):
        assert probe.check_s1c({"anvil_js_error": "x"}, "aa")[0] == "FAIL"

    def test_s3_needs_all_three_timings(self, probe):
        ok = {"ms100000": "1", "ms300000": "3", "ms600000": "6"}
        assert probe.check_s3(ok)[0] == "PASS"
        assert probe.check_s3({"ms100000": "1"})[0] == "FAIL"

    def test_a_result_line_is_one_line(self, probe):
        assert probe.format_line("S1a", "FAIL", "a\nb") == "S1a FAIL a b"


class TestCryptoDeriveOverlay:
    OVERLAY = SPIKES / "crypto_derive" / "app"
    FORM = OVERLAY / "client_code" / "DeriveSpike"

    def test_every_dom_node_lookup_is_in_the_template(self):
        code = (self.FORM / "__init__.py").read_text(encoding="utf-8")
        template = (self.FORM / "form_template.html").read_text(encoding="utf-8")
        looked_up = set(re.findall(r"""dom_nodes\[\s*["']([^"']+)["']""", code))
        declared = set(
            re.findall(r"""anvil:dom-node\s*=\s*["']([^"']+)["']""", template)
        )
        assert looked_up
        assert looked_up <= declared

    def test_every_button_handler_exists(self):
        code = (self.FORM / "__init__.py").read_text(encoding="utf-8")
        template = (self.FORM / "form_template.html").read_text(encoding="utf-8")
        handlers = re.findall(r"anvil:on-dom:click=\"self\.(\w+)\"", template)
        assert len(handlers) == 4
        for name in handlers:
            assert f"def {name}(" in code

    def test_the_template_defines_the_function_call_js_uses(self):
        template = (self.FORM / "form_template.html").read_text(encoding="utf-8")
        code = (self.FORM / "__init__.py").read_text(encoding="utf-8")
        assert "window.irisDerive = async function" in template
        assert 'call_js("irisDerive"' in code

    def test_the_server_timing_callable_times_each_count(self, monkeypatch):
        import importlib.util

        path = self.OVERLAY / "server_code" / "spike_kdf.py"
        spec = importlib.util.spec_from_file_location("spike_kdf_under_test", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        monkeypatch.setattr(module, "ITERATIONS", (10, 20, 30))
        timings = module.spike_kdf_timing()
        assert list(timings) == ["10", "20", "30"]
        assert all(isinstance(v, float) and v >= 0 for v in timings.values())

    def test_the_server_timing_defaults_are_100k_300k_600k(self):
        import importlib.util

        path = self.OVERLAY / "server_code" / "spike_kdf.py"
        spec = importlib.util.spec_from_file_location("spike_kdf_defaults", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.ITERATIONS == (100_000, 300_000, 600_000)
