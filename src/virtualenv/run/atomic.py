"""Atomic, crash-safe publication of a created virtual environment.

Multiple processes may ask for an environment at the same destination, and creation, seeding or activation
generation may fail (or be interrupted) halfway. To make the destination appear as a whole only once everything
succeeded, :class:`AtomicEnvironment`:

1. serializes concurrent transactions for a given destination with a cross-process file lock,
2. builds the environment in a temporary staging directory next to the destination (same file system, same depth,
   so symlinks and the final ``os.replace`` keep working) when creating a new environment or replacing one with
   ``--clear``,
3. publishes it with a backup/rename/rename sequence, restoring the previous environment if publishing fails,
4. on any failure or interruption deletes the staging directory and leaves the original destination untouched,
5. sweeps staging/backup leftovers of crashed transactions (the operating system releases the lock when a
   process dies) the next time a transaction for the destination starts.

When an environment already exists at the destination and ``--clear`` was not requested the historical
in-place merge semantics apply: virtualenv only overwrites files it owns and keeps everything else (user files,
a pre-existing ``CACHEDIR.TAG`` / ``.gitignore``), so the build happens directly at the destination. The
cross-process lock still serializes such updates and no temporary resources are created.
"""

from __future__ import annotations

import logging
import os
import secrets
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

from filelock import FileLock, Timeout

from virtualenv.util.lock import ReentrantFileLock
from virtualenv.util.path import safe_delete

if TYPE_CHECKING:
    from types import TracebackType

    from virtualenv.create.creator import Creator

LOGGER = logging.getLogger(__name__)

_STAGING_TEMPLATE = ".{name}.virtualenv-staging-"
_BACKUP_TEMPLATE = ".{name}.virtualenv-backup-"
_LOCK_KEY_TEMPLATE = ".{name}.virtualenv-create"


class AtomicEnvironment:
    """Build a virtual environment in a staging directory and publish it atomically.

    Use as a context manager around the create/seed/activate pipeline and call :meth:`commit` once every step
    succeeded; exiting the context without a commit (including because of an exception or interrupt) rolls the
    build back::

        with AtomicEnvironment(creator) as transaction:
            creator.run()
            seeder.run(creator)
            ...
            transaction.commit()
    """

    def __init__(self, creator: Creator) -> None:
        self._creator = creator
        self._final = Path(creator.dest)
        self._parent = self._final.parent
        self._staging: Path | None = None
        self._in_place = False
        self._committed = False
        self._lock: ReentrantFileLock | None = None
        self._lock_context = None
        self._staging_prefix = _STAGING_TEMPLATE.format(name=self._final.name)
        self._backup_prefix = _BACKUP_TEMPLATE.format(name=self._final.name)
        lock_key = _LOCK_KEY_TEMPLATE.format(name=self._final.name)
        self._lock_file = self._parent / f"{lock_key}.lock"

    def __enter__(self) -> AtomicEnvironment:
        # the lock (and the staging directory) live next to the destination so they are on the same file system
        self._parent.mkdir(parents=True, exist_ok=True)
        self._lock = ReentrantFileLock(self._parent)
        lock_key = _LOCK_KEY_TEMPLATE.format(name=self._final.name)
        self._lock_context = self._lock.lock_for_key(lock_key)
        self._lock_context.__enter__()
        # a previous process may have died mid-transaction; clean up before doing anything
        self._recover()
        if self._use_in_place_build():
            # existing destination, no --clear: keep the historical in-place merge semantics so files virtualenv
            # does not own (user content, a pre-existing CACHEDIR.TAG/.gitignore) are preserved
            self._in_place = True
            self._staging = self._final
            LOGGER.debug("updating existing virtual environment in place at %s", self._final)
        else:
            self._staging = Path(tempfile.mkdtemp(prefix=self._staging_prefix, dir=str(self._parent)))
            LOGGER.debug("building virtual environment in staging %s", self._staging)
        self._creator.redirect(self._staging)
        return self

    def _use_in_place_build(self) -> bool:
        return not self._creator.clear and (self._final.exists() or self._final.is_symlink())

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None or not self._committed:
                # the pipeline failed/was interrupted, or it finished without committing: nothing was published, so
                # throw the half build away and point the creator back at the (untouched) destination
                self._abort()
        finally:
            if self._lock_context is not None:
                self._lock_context.__exit__(None, None, None)
                self._lock_context = None
            self._remove_lock_file()

    def commit(self) -> None:
        """Publish the staging build at the destination.

        Raises (and rolls the staging build back) if the environment cannot be moved into place. Call only after
        every creation step succeeded.
        """
        if self._in_place:
            # the build happened directly at the destination, there is nothing to move or rewrite
            self._committed = True
            return
        staging = self._require_staging()
        try:
            self._fixup_shebangs(staging)
            self._publish(staging)
        except BaseException:
            self._abort()
            raise
        self._staging = None
        self._committed = True
        self._creator.redirect(self._final)

    def _abort(self) -> None:
        if self._staging is not None and not self._in_place:
            with suppress(OSError):
                safe_delete(self._staging)
        self._staging = None
        self._in_place = False
        self._creator.redirect(self._final)

    # -- publishing -----------------------------------------------------------------------------------------------

    def _publish(self, staging: Path) -> None:
        if not self._final.exists() and not self._final.is_symlink():
            os.replace(staging, self._final)
            LOGGER.debug("published new virtual environment at %s", self._final)
            return
        # os.replace cannot atomically replace a non-empty directory; move the current one aside, move the new one
        # in, and only then discard the old one. The destination is briefly absent in between, but the cross-process
        # lock keeps other virtualenv transactions out of that window.
        backup = self._unique_sibling(self._backup_prefix)
        os.rename(self._final, backup)
        try:
            os.replace(staging, self._final)
        except OSError:
            # bring the previous environment back before surfacing the failure
            with suppress(OSError):
                os.replace(backup, self._final)
            raise
        LOGGER.debug("replaced virtual environment at %s (previous one at %s)", self._final, backup)
        safe_delete(backup)

    def _unique_sibling(self, prefix: str) -> Path:
        while True:
            candidate = self._parent / f"{prefix}{secrets.token_hex(4)}"
            if not candidate.exists() and not candidate.is_symlink():
                return candidate

    def _fixup_shebangs(self, staging: Path) -> None:
        # console scripts (pip, setuptools, ...) embed the running interpreter path. While the environment lived
        # in staging that was the staging path, rewrite it to the final destination before publish. The path may
        # appear on the shebang line (``#!staging/bin/python``) or, when the path contains characters a shebang
        # cannot represent (spaces, ...), inside a ``#!/bin/sh`` re-exec wrapper on a later line.
        physical = os.fsencode(str(staging))
        logical = os.fsencode(str(self._final))
        bin_dir = Path(self._creator.bin_dir)
        if not bin_dir.is_dir():
            return
        for script in bin_dir.iterdir():
            if script.is_symlink() or not script.is_file():
                continue
            try:
                with script.open("rb") as handle:
                    content = handle.read()
            except OSError:
                continue
            # only touch text scripts: a copied interpreter binary is a regular file too, and changing byte
            # offsets inside it would corrupt it
            if not content.startswith(b"#!") or physical not in content:
                continue
            LOGGER.debug("rewrite staging path in console script %s", script)
            with script.open("wb") as handle:
                handle.write(content.replace(physical, logical))

    # -- crash recovery -------------------------------------------------------------------------------------------

    def _recover(self) -> None:
        leftovers = [
            i
            for i in self._parent.iterdir()
            if i.name.startswith((self._staging_prefix, self._backup_prefix))
        ]
        backups = sorted(
            (i for i in leftovers if i.name.startswith(self._backup_prefix)),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not self._final.exists() and not self._final.is_symlink() and backups:
            # a crash between moving the old environment aside and moving the new one in: restore it
            newest = backups[0]
            LOGGER.warning("recovering virtual environment %s from interrupted update %s", self._final, newest)
            os.rename(newest, self._final)
            leftovers.remove(newest)
            backups.pop(0)
        # anything still here is a dead transaction's staging directory or a superseded backup
        for leftover in leftovers:
            LOGGER.warning("removing leftover of an interrupted virtual environment creation: %s", leftover)
            with suppress(OSError):
                safe_delete(leftover)

    # -- lock housekeeping ----------------------------------------------------------------------------------------

    def _remove_lock_file(self) -> None:
        # delete the lock file only when nobody else holds or waits for it; re-acquiring it ourselves for an instant
        # is race free: if another process still holds the old lock we cannot acquire it and leave the file alone,
        # otherwise everyone that arrives afterwards creates/locks a fresh inode
        probe = FileLock(str(self._lock_file))
        try:
            probe.acquire(timeout=0)
        except Timeout:
            return
        except OSError:
            return
        try:
            with suppress(OSError):
                os.unlink(self._lock_file)
        finally:
            with suppress(OSError):
                probe.release()

    def _require_staging(self) -> Path:
        if self._staging is None:
            msg = "the atomic environment was not entered or already committed"
            raise RuntimeError(msg)
        return self._staging


__all__ = [
    "AtomicEnvironment",
]
