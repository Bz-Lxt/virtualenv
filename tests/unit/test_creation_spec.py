from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Importing the cache module interrogates the running interpreter in-process, which makes
# setuptools' vendored distutils set os.environ["PLAT"] once (distutils.util.check_environ).
# Trigger it at collection time, before the env-stability fixture snapshots the environment.
import python_discovery._cached_py_info  # ruff:ignore[unused-import]

from virtualenv.__main__ import run_with_catch
from virtualenv.run import cli_run, export_creation_spec, session_via_cli, session_via_spec
from virtualenv.run.spec import CreationSpec, SpecDriftError, SpecError


@pytest.fixture
def dest(tmp_path: Path) -> Path:
    return tmp_path / "venv"


@pytest.fixture
def spec_path(tmp_path: Path) -> Path:
    return tmp_path / "creation-spec.json"


def _export(args: list[str], spec_path: Path) -> CreationSpec:
    session = session_via_cli(args)
    assert session.options is not None
    export_creation_spec(session, session.options, spec_path)
    return CreationSpec.load(spec_path)


def _run_session(session) -> None:
    with session:
        session.run()


def _dist_info(dest: Path, distribution: str) -> Path | None:
    purelib = dest / "lib"
    candidates = list(purelib.rglob(f"{distribution}-*.dist-info"))
    return candidates[0] if candidates else None


# -- export ----------------------------------------------------------------


def test_export_captures_resolved_deterministic_spec(dest: Path, spec_path: Path) -> None:
    spec = _export([str(dest), "--prompt", "my-env", "--copies"], spec_path)
    data = spec.to_dict()

    assert data["spec_version"] == 1
    assert isinstance(data["virtualenv_version"], str)
    assert data["virtualenv_version"]

    # concrete plugin selection is recorded, not the ambiguous selector input
    assert data["creator"]["key"] == "builtin"
    assert data["creator"]["type"] == type(session_via_cli([str(dest)]).creator).__name__
    assert data["seeder"] == {"key": "app-data", "type": "FromAppData", "enabled": True}
    assert {a["type"] for a in data["activators"]} >= {"BashActivator", "PythonActivator"}

    # configuration sources are folded into concrete option values plus provenance
    assert data["options"]["dest"] == str(dest)
    assert data["options"]["prompt"] == "my-env"
    assert data["options"]["copies"] is True
    assert data["option_sources"]["prompt"] == "cli"

    # the discovered interpreter is pinned by identity, location and content hash
    identity = data["interpreter"]["identity"]
    assert identity["implementation"] == "CPython"
    assert identity["version_info"][:2] == [sys.version_info.major, sys.version_info.minor]
    assert data["interpreter"]["system_executable"]
    assert re.fullmatch(r"[0-9a-f]{64}", data["interpreter"]["executable_sha256"])
    assert data["interpreter"]["info"]["system_executable"] == data["interpreter"]["system_executable"]

    # every seed artifact is pinned by existing path and SHA-256
    wheels = {w["distribution"]: w for w in data["seeds"]["wheels"]}
    assert set(wheels) >= {"pip"}
    for wheel in wheels.values():
        assert re.fullmatch(r"[0-9a-f]{64}", wheel["sha256"])
        assert Path(wheel["path"]).is_file()
        assert wheel["filename"] == Path(wheel["path"]).name


def test_export_is_byte_deterministic(dest: Path, spec_path: Path) -> None:
    args = [str(dest), "--prompt", "stable", "--activators", "bash"]
    first = _export(args, spec_path)
    second_path = spec_path.with_name("second.json")
    second = _export(args, second_path)
    assert first.dump_json() == second.dump_json()


def test_export_round_trips_through_json(dest: Path, spec_path: Path) -> None:
    spec = _export([str(dest)], spec_path)
    assert CreationSpec.load(spec_path).to_dict() == spec.to_dict()


def test_export_does_not_create_environment(dest: Path, spec_path: Path) -> None:
    with pytest.raises(SystemExit) as context:
        cli_run([str(dest), "--export-spec", str(spec_path)])
    assert context.value.code == 0
    assert not dest.exists()
    assert spec_path.is_file()


def test_export_spec_flags_are_not_part_of_the_spec(dest: Path, spec_path: Path) -> None:
    data = _export([str(dest), "--export-spec", str(spec_path)], spec_path).to_dict()
    assert "export_spec" not in data["options"]
    assert "from_spec" not in data["options"]
    # logging controls describe the invocation, not the environment, and accumulate during option parsing
    assert "verbose" not in data["options"]
    assert "quiet" not in data["options"]


# -- replay ----------------------------------------------------------------


def test_replay_creates_environment_pinned_by_spec(dest: Path, spec_path: Path) -> None:
    spec = _export([str(dest)], spec_path)
    pinned_versions = {w["distribution"]: w["version"] for w in spec.to_dict()["seeds"]["wheels"]}

    session = session_via_spec(spec_path)
    # the seeder is pinned to the verified wheels and therefore cannot periodically update or download
    assert session.seeder._pinned_wheels is not None  # ruff:ignore[private-member-access]
    assert set(session.seeder._pinned_wheels) == set(pinned_versions)  # ruff:ignore[private-member-access]
    _run_session(session)

    assert dest.is_dir()
    assert (dest / "pyvenv.cfg").is_file()
    assert (dest / "bin" / "activate").is_file()
    pip_info = _dist_info(dest, "pip")
    assert pip_info is not None
    assert pip_info.name == f"pip-{pinned_versions['pip']}.dist-info"


def test_replay_is_lossless_across_processes(dest: Path, spec_path: Path) -> None:
    _export([str(dest), "--activators", "bash"], spec_path)
    assert not dest.exists()

    result = subprocess.run(
        [sys.executable, "-m", "virtualenv", "--from-spec", str(spec_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert dest.is_dir()
    assert (dest / "bin" / "activate").is_file()
    probe = subprocess.run(
        [str(dest / "bin" / "python"), "-c", "import pip; print(pip.__version__)"],
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, probe.stderr
    recorded = next(
        w["version"]
        for w in json.loads(spec_path.read_text(encoding="utf-8"))["seeds"]["wheels"]
        if w["distribution"] == "pip"
    )
    assert probe.stdout.strip() == recorded


def test_replay_ignores_configuration_sources(dest: Path, spec_path: Path) -> None:
    _export([str(dest)], spec_path)
    hostile_env = dict(os.environ)
    hostile_env["VIRTUALENV_PROMPT"] = "hacked"
    hostile_env["VIRTUALENV_CLEAR"] = "true"
    hostile_env["VIRTUALENV_SYSTEM_SITE_PACKAGES"] = "true"

    session = session_via_spec(spec_path, env=hostile_env)
    assert session.creator.prompt is None
    assert session.creator.clear is False
    assert session.creator.enable_system_site_package is False


def test_replay_no_seed(dest: Path, spec_path: Path) -> None:
    spec = _export([str(dest), "--no-seed"], spec_path)
    assert spec.to_dict()["seeds"]["wheels"] == []
    assert spec.to_dict()["seeder"]["enabled"] is False

    _run_session(session_via_spec(spec_path))
    assert (dest / "pyvenv.cfg").is_file()
    assert _dist_info(dest, "pip") is None


# -- drift rejection -------------------------------------------------------


def _tampered_spec(base: CreationSpec, mutate, path: Path) -> Path:
    data = copy.deepcopy(base.to_dict())
    mutate(data)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda d: d["interpreter"]["identity"]["version_info"].__setitem__(2, 999), id="interpreter-identity"
        ),
        pytest.param(
            lambda d: d["interpreter"].__setitem__("system_executable", "/no/such/python9.9"), id="interpreter-missing"
        ),
        pytest.param(lambda d: d["interpreter"].__setitem__("executable_sha256", "f" * 64), id="interpreter-sha256"),
        pytest.param(lambda d: d["seeds"]["wheels"][0].__setitem__("sha256", "0" * 64), id="seed-sha256"),
        pytest.param(
            lambda d: d["seeds"]["wheels"][0].__setitem__("path", d["seeds"]["wheels"][0]["path"] + ".gone"),
            id="seed-missing",
        ),
        pytest.param(lambda d: d["creator"].__setitem__("type", "EvilCreator"), id="creator-plugin"),
        pytest.param(lambda d: d["activators"][0].__setitem__("type", "ZshActivator"), id="activator-plugin"),
    ],
)
def test_replay_refuses_on_drift(dest: Path, spec_path: Path, tmp_path: Path, mutate) -> None:
    spec = _export([str(dest)], spec_path)
    tampered = _tampered_spec(spec, mutate, tmp_path / "tampered.json")
    with pytest.raises(SpecDriftError):
        session_via_spec(tampered)
    assert not dest.exists()


def test_drift_is_reported_even_when_export_was_quiet(dest: Path, spec_path: Path, tmp_path: Path, capsys) -> None:

    spec = _export([str(dest), "-q"], spec_path)
    tampered = _tampered_spec(
        spec,
        lambda d: d["interpreter"]["identity"]["version_info"].__setitem__(2, 999),
        tmp_path / "tampered.json",
    )
    with pytest.raises(SystemExit) as context:
        run_with_catch(["--from-spec", str(tampered)])
    assert context.value.code == 1
    assert "SpecDriftError" in capsys.readouterr().out
    assert not dest.exists()


def test_replay_refuses_unknown_spec_version(dest: Path, spec_path: Path, tmp_path: Path) -> None:
    spec = _export([str(dest)], spec_path)
    tampered = _tampered_spec(spec, lambda d: d.__setitem__("spec_version", 999), tmp_path / "future.json")
    with pytest.raises(SpecError, match="unsupported creation spec version"):
        session_via_spec(tampered)


def test_replay_refuses_malformed_spec(spec_path: Path) -> None:
    spec_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SpecError, match="not valid JSON"):
        CreationSpec.load(spec_path)


def test_replay_refuses_missing_spec_file(tmp_path: Path) -> None:
    with pytest.raises(SpecError, match="cannot read creation spec"):
        CreationSpec.load(tmp_path / "absent.json")


def test_export_and_replay_flags_are_mutually_exclusive(dest: Path, spec_path: Path) -> None:
    with pytest.raises(SystemExit) as context:
        cli_run([str(dest), "--export-spec", str(spec_path), "--from-spec", str(spec_path)])
    assert context.value.code == 2


def test_help_documents_the_creation_spec_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as context:
        cli_run(["--help"])
    assert context.value.code == 0
    out = capsys.readouterr().out
    assert "--export-spec" in out
    assert "--from-spec" in out
    assert "creation spec" in out
