from __future__ import annotations

import os
import sys
from subprocess import Popen
from typing import TYPE_CHECKING

from virtualenv import cli_run
from virtualenv.util.subprocess import run_cmd

if TYPE_CHECKING:
    from pathlib import Path


def _leftovers(folder: Path, name: str) -> list[str]:
    return [
        entry.name
        for entry in folder.iterdir()
        if entry.name != name
        and (
            ".virtualenv-staging-" in entry.name
            or ".virtualenv-backup-" in entry.name
            or entry.name.endswith(".lock")
        )
    ]


def test_concurrent_creation_of_same_path(tmp_path: Path) -> None:
    target = tmp_path / "venv"
    args = [sys.executable, "-m", "virtualenv", str(target), "--no-seed", "--activators", ""]

    processes = [Popen(args) for _ in range(3)]
    codes = [process.wait() for process in processes]

    assert codes == [0, 0, 0]
    assert (target / "pyvenv.cfg").is_file()
    assert _leftovers(tmp_path, "venv") == []

    code, _, _ = run_cmd([str(target / ("Scripts" if os.name == "nt" else "bin") / "python"), "-c", "print(1)"])
    assert code == 0


def test_seeded_console_scripts_use_final_path(tmp_path: Path) -> None:
    target = tmp_path / "venv"
    cli_run([str(target)])

    scripts = target / ("Scripts" if os.name == "nt" else "bin")
    pip_scripts = [path for path in scripts.iterdir() if path.name.startswith("pip") and path.is_file()]
    assert pip_scripts
    for script in pip_scripts:
        content = script.read_text(encoding="utf-8", errors="ignore")
        assert "virtualenv-staging" not in content.splitlines()[0]

    code, out, err = run_cmd([str(scripts / "pip"), "--version", "--disable-pip-version-check"])
    assert code == 0, err
    assert str(target) in out or str(target) in err or "pip" in out


def test_crash_leftovers_are_swept_on_next_run(tmp_path: Path) -> None:
    target = tmp_path / "venv"
    # interrupted swap: the previous environment was moved aside but the process died before publishing
    backup = tmp_path / ".venv.virtualenv-backup-deadbeef"
    backup.mkdir()
    (backup / "pyvenv.cfg").write_text("home = old\n", encoding="utf-8")
    stale = tmp_path / "venv2-unrelated-dir"  # a lookalike other destination must not be touched
    stale.mkdir()
    stale_staging = tmp_path / ".venv.virtualenv-staging-aaaa"
    stale_staging.mkdir()

    cli_run([str(target), "--no-seed", "--activators", ""])

    assert (target / "pyvenv.cfg").is_file()
    assert stale.is_dir()  # belonged to a different destination name
    assert _leftovers(tmp_path, "venv") == []
