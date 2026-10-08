from __future__ import annotations

import subprocess
from argparse import Namespace
from shutil import which
from typing import TYPE_CHECKING

import pytest

from virtualenv.activation import NushellActivator
from virtualenv.info import IS_WIN
from virtualenv.run import cli_run

if TYPE_CHECKING:
    from pathlib import Path


def test_nushell_tkinter_generation(tmp_path) -> None:
    # GIVEN
    class MockInterpreter:
        pass

    interpreter = MockInterpreter()
    interpreter.tcl_lib = "/path/to/tcl"
    interpreter.tk_lib = "/path/to/tk"
    quoted_tcl_path = NushellActivator.quote(interpreter.tcl_lib)
    quoted_tk_path = NushellActivator.quote(interpreter.tk_lib)

    class MockCreator:
        def __init__(self, dest) -> None:
            self.dest = dest
            self.bin_dir = dest / "bin"
            self.bin_dir.mkdir()
            self.interpreter = interpreter
            self.pyenv_cfg = {}
            self.env_name = "my-env"

    creator = MockCreator(tmp_path)
    options = Namespace(prompt=None)
    activator = NushellActivator(options)

    # WHEN
    activator.generate(creator)
    content = (creator.bin_dir / "activate.nu").read_text(encoding="utf-8")

    # THEN
    # PKG_CONFIG_PATH is always set
    assert "let old_pkg_config_path = if (has-env 'PKG_CONFIG_PATH')" in content
    assert "let new_pkg_config_path = " in content
    assert "PKG_CONFIG_PATH: $new_pkg_config_path" in content

    # TCL/TK are exported only when the environment actually provides a path;
    # the value quoted as a nushell raw string and the activation is gated on
    # the embedded value being non-empty.
    assert f"let tcl_library = {quoted_tcl_path}" in content
    assert "if (not ($tcl_library | is-empty))" in content
    assert "insert TCL_LIBRARY $tcl_library" in content
    assert f"let tk_library = {quoted_tk_path}" in content
    assert "if (not ($tk_library | is-empty))" in content
    assert "insert TK_LIBRARY $tk_library" in content

    # Layered deactivation is an env-aware command: it pops the most recent
    # activation layer and restores the captured snapshot.
    assert "export def --env deactivate [--non-destructive]" in content
    assert "export alias deactivate = overlay hide activate" not in content


def test_nushell(activation_tester_class, activation_tester) -> None:
    class Nushell(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(NushellActivator, session, which("nu"), "activate.nu", "nu")

            self.activate_cmd = "overlay use"
            self.unix_line_ending = not IS_WIN

        def print_prompt(self) -> str:
            return r"print $env.VIRTUAL_PREFIX"

        def activate_call(self, script):
            # Commands are called without quotes in Nushell
            cmd = self.activate_cmd
            scr = self.quote(str(script))
            return f"{cmd} {scr}".strip()

    activation_tester(Nushell)


def test_nushell_activation_modes(tmp_path: Path) -> None:
    """Behaviour of the three loading styles.

    `source` is rejected with an actionable error. Both `use *` and a named overlay activate the environment and
    `deactivate` restores it (the stack lives in `$env`, so the overlay name is irrelevant to deactivation).

    """
    nu = which("nu")
    if nu is None:
        pytest.skip("nu not installed")

    activate_nu = cli_run(["--without-pip", str(tmp_path / "venv")]).creator.bin_dir / "activate.nu"
    quoted = NushellActivator.quote(str(activate_nu))

    # `to nuon` re-quotes the path so it remains valid nushell syntax after string interpolation.
    script = f"""\
let path = {quoted}
let r1 = (^nu --commands $"source ($path | to nuon)" | complete)
if ($r1.exit_code == 0) {{ error make {{ msg: "expected source to fail" }} }}
if not ("meant to be used with `overlay use`" in $r1.stderr) {{ error make {{ msg: "source hint missing" }} }}
let r2 = (^nu --commands $"use ($path | to nuon) *; deactivate; print ($env | get --optional VIRTUAL_ENV | to json)" | complete)
if ($r2.exit_code != 0) {{ error make {{ msg: $"use-star failed: ($r2.stderr)" }} }}
if ($r2.stdout | str trim) != "null" {{ error make {{ msg: $"use-star did not restore env: ($r2.stdout)" }} }}
let r3 = (^nu --commands $"overlay use ($path | to nuon) as myenv; deactivate; print ($env | get --optional VIRTUAL_ENV | to json)" | complete)
if ($r3.exit_code != 0) {{ error make {{ msg: $"named overlay failed: ($r3.stderr)" }} }}
if ($r3.stdout | str trim) != "null" {{ error make {{ msg: $"named overlay did not restore env: ($r3.stdout)" }} }}
"""
    result = subprocess.run(
        [nu, "--commands", script], capture_output=True, text=True, encoding="utf-8", timeout=60, check=False
    )
    assert result.returncode == 0, result.stderr
