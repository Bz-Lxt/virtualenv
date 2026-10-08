from __future__ import annotations

from pathlib import Path

import pytest
from virtualenv import cli_run
from virtualenv.run.atomic import AtomicEnvironment


class FakeCreator:
    """Minimal stand-in for the parts of :class:`Creator` the transaction drives."""

    def __init__(self, dest: Path, clear: bool = False) -> None:
        self.dest = Path(dest)
        self.clear = clear
        self.redirects: list[Path] = []

    def redirect(self, root: Path) -> None:
        self.redirects.append(Path(root))

    @property
    def bin_dir(self) -> Path:
        return self.redirects[-1] / "bin"


def _temp_entries(folder: Path) -> list[str]:
    return [
        path.name
        for path in folder.iterdir()
        if path.name != "venv"
        and (".virtualenv-staging-" in path.name or ".virtualenv-backup-" in path.name or path.name.endswith(".lock"))
    ]


def test_exit_without_commit_removes_staging_and_lock(tmp_path: Path) -> None:
    final = tmp_path / "venv"
    creator = FakeCreator(final)

    with AtomicEnvironment(creator):
        staging = creator.redirects[-1]
        assert staging.is_dir()
        (staging / "half-built").write_text("x", encoding="utf-8")

    assert not final.exists()
    assert not staging.exists()
    assert _temp_entries(tmp_path) == []
    assert creator.redirects[-1] == final


def test_commit_publishes_staging(tmp_path: Path) -> None:
    final = tmp_path / "venv"
    creator = FakeCreator(final)

    with AtomicEnvironment(creator) as transaction:
        staging = creator.redirects[-1]
        (staging / "pyvenv.cfg").write_text("home = x\n", encoding="utf-8")
        transaction.commit()

    assert (final / "pyvenv.cfg").is_file()
    assert creator.redirects[-1] == final
    assert _temp_entries(tmp_path) == []


def test_shebang_is_rewritten_to_final_path(tmp_path: Path) -> None:
    final = tmp_path / "venv"
    creator = FakeCreator(final)

    with AtomicEnvironment(creator) as transaction:
        staging = creator.redirects[-1]
        bin_dir = staging / "bin"
        bin_dir.mkdir()
        script = bin_dir / "pip"
        script.write_text(f"#!{staging / 'bin' / 'python'}\n# code\n", encoding="utf-8")
        # paths with spaces get a /bin/sh re-exec wrapper whose interpreter reference is not on the shebang line
        wrapped = bin_dir / "pipw"
        wrapped.write_text(
            "#!/bin/sh\n"
            f"'''exec' \"{staging / 'bin' / 'python'}\" \"$0\" \"$@\"\n"
            "'''\n",
            encoding="utf-8",
        )
        transaction.commit()

    published = final / "bin" / "pip"
    first_line = published.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == f"#!{final / 'bin' / 'python'}"
    assert "staging" not in first_line
    wrapped_content = (final / "bin" / "pipw").read_text(encoding="utf-8")
    assert str(staging) not in wrapped_content
    assert str(final / "bin" / "python") in wrapped_content


def test_recover_restores_backup_when_destination_missing(tmp_path: Path) -> None:
    final = tmp_path / "venv"
    backup = tmp_path / ".venv.virtualenv-backup-deadbeef"
    backup.mkdir()
    (backup / "pyvenv.cfg").write_text("home = old\n", encoding="utf-8")
    stale_staging = tmp_path / ".venv.virtualenv-staging-aaaa"
    stale_staging.mkdir()
    (stale_staging / "junk").write_text("x", encoding="utf-8")

    with AtomicEnvironment(FakeCreator(final)):
        assert (final / "pyvenv.cfg").read_text(encoding="utf-8") == "home = old\n"
        assert not stale_staging.exists()

    assert _temp_entries(tmp_path) == []


def test_recover_removes_backup_when_destination_exists(tmp_path: Path) -> None:
    final = tmp_path / "venv"
    final.mkdir()
    (final / "pyvenv.cfg").write_text("home = new\n", encoding="utf-8")
    backup = tmp_path / ".venv.virtualenv-backup-deadbeef"
    backup.mkdir()
    stale_staging = tmp_path / ".venv.virtualenv-staging-aaaa"
    stale_staging.mkdir()

    with AtomicEnvironment(FakeCreator(final)):
        assert (final / "pyvenv.cfg").read_text(encoding="utf-8") == "home = new\n"

    assert not backup.exists()
    assert not stale_staging.exists()
    assert _temp_entries(tmp_path) == []


def test_existing_destination_without_clear_builds_in_place(tmp_path: Path) -> None:
    final = tmp_path / "venv"
    final.mkdir()
    (final / "user-file.txt").write_text("keep me", encoding="utf-8")
    creator = FakeCreator(final)

    with AtomicEnvironment(creator) as transaction:
        assert creator.redirects[-1] == final
        (final / "pyvenv.cfg").write_text("home = x\n", encoding="utf-8")
        transaction.commit()

    # the user file survives and no staging/backup directory was ever created
    assert (final / "user-file.txt").read_text(encoding="utf-8") == "keep me"
    assert (final / "pyvenv.cfg").is_file()
    assert creator.redirects[-1] == final
    assert _temp_entries(tmp_path) == []


def test_existing_destination_with_clear_uses_staging(tmp_path: Path) -> None:
    final = tmp_path / "venv"
    final.mkdir()
    (final / "old.txt").write_text("old", encoding="utf-8")
    creator = FakeCreator(final, clear=True)

    with AtomicEnvironment(creator) as transaction:
        staging = creator.redirects[-1]
        assert staging != final
        (staging / "new.txt").write_text("new", encoding="utf-8")
        transaction.commit()

    assert not (final / "old.txt").exists()
    assert (final / "new.txt").read_text(encoding="utf-8") == "new"
    assert _temp_entries(tmp_path) == []


def test_commit_failure_restores_existing_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    final = tmp_path / "venv"
    final.mkdir()
    (final / "pyvenv.cfg").write_text("home = keep\n", encoding="utf-8")
    creator = FakeCreator(final, clear=True)

    import virtualenv.run.atomic as atomic

    real_replace = atomic.os.replace

    def fail_replace(src, dst):  # noqa: ANN001
        if Path(src).name == staging.name:
            msg = "simulated publish failure"
            raise OSError(msg)
        return real_replace(src, dst)

    monkeypatch.setattr(atomic.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated publish failure"):  # noqa: SIM117
        with AtomicEnvironment(creator) as transaction:
            staging = creator.redirects[-1]
            (staging / "built").write_text("x", encoding="utf-8")
            transaction.commit()

    assert (final / "pyvenv.cfg").read_text(encoding="utf-8") == "home = keep\n"
    assert not staging.exists()
    assert _temp_entries(tmp_path) == []


def test_successful_create_has_no_temporary_residue(tmp_path: Path) -> None:
    dest = tmp_path / "venv"
    session = cli_run([str(dest), "--no-seed", "--activators", "bash"])

    assert (dest / "pyvenv.cfg").is_file()
    assert session.creator.root.resolve() == dest.resolve()
    activate = dest / "bin" / "activate"
    assert str(dest) in activate.read_text(encoding="utf-8")
    assert "virtualenv-staging" not in activate.read_text(encoding="utf-8")
    assert "virtualenv-staging" not in (dest / "pyvenv.cfg").read_text(encoding="utf-8")
    assert _temp_entries(tmp_path) == []


def test_failure_on_fresh_destination_leaves_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from virtualenv.activation.bash import BashActivator

    def fail_generate(self, creator):  # noqa: ANN001
        msg = "activation exploded"
        raise RuntimeError(msg)

    monkeypatch.setattr(BashActivator, "generate", fail_generate)
    dest = tmp_path / "venv"

    with pytest.raises(RuntimeError, match="activation exploded"):
        cli_run([str(dest), "--no-seed", "--activators", "bash"])

    assert not dest.exists()
    assert _temp_entries(tmp_path) == []


def test_failure_restores_previous_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from virtualenv.activation.bash import BashActivator

    dest = tmp_path / "venv"
    cli_run([str(dest), "--no-seed", "--activators", "bash"])
    marker = dest / "user-file.txt"
    marker.write_text("keep me", encoding="utf-8")
    pyenv_cfg_before = (dest / "pyvenv.cfg").read_text(encoding="utf-8")

    def fail_generate(self, creator):  # noqa: ANN001
        msg = "activation exploded"
        raise RuntimeError(msg)

    monkeypatch.setattr(BashActivator, "generate", fail_generate)

    with pytest.raises(RuntimeError, match="activation exploded"):
        cli_run([str(dest), "--no-seed", "--activators", "bash"])

    assert dest.is_dir()
    assert marker.read_text(encoding="utf-8") == "keep me"
    assert (dest / "pyvenv.cfg").read_text(encoding="utf-8") == pyenv_cfg_before
    assert _temp_entries(tmp_path) == []


def test_clear_failure_restores_previous_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from virtualenv.activation.bash import BashActivator

    dest = tmp_path / "venv"
    cli_run([str(dest), "--no-seed", "--activators", "bash"])
    marker = dest / "user-file.txt"
    marker.write_text("keep me", encoding="utf-8")
    pyenv_cfg_before = (dest / "pyvenv.cfg").read_text(encoding="utf-8")

    def fail_generate(self, creator):  # noqa: ANN001
        msg = "activation exploded"
        raise RuntimeError(msg)

    monkeypatch.setattr(BashActivator, "generate", fail_generate)

    with pytest.raises(RuntimeError, match="activation exploded"):
        cli_run([str(dest), "--no-seed", "--activators", "bash", "--clear"])

    # the --clear replacement never published, so the previous environment is still in place
    assert dest.is_dir()
    assert marker.read_text(encoding="utf-8") == "keep me"
    assert (dest / "pyvenv.cfg").read_text(encoding="utf-8") == pyenv_cfg_before
    assert _temp_entries(tmp_path) == []
