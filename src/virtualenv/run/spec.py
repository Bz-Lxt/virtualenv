"""Resolved, deterministic and verifiable creation specifications.

The same virtualenv command line can produce different environments over time because the effective configuration is
the product of four inputs that are each resolved lazily and may change between invocations:

* configuration sources (command line, environment variables, ini files and defaults)
* plugin selection (entry points, creator/seeder availability for the interpreter)
* interpreter discovery (``PATH``, specifiers, discovery cache)
* seed package resolution (the bundle, extra search dirs, the 14 day periodic update and PyPI downloads)

A :class:`CreationSpec` captures the *resolved* outcome of all four inputs after a session has been planned: concrete
option values together with their provenance, the selected plugin types, a fingerprint of the discovered interpreter
and every seed wheel pinned by path and SHA-256. The specification is plain JSON, so it can be exported in one process
and replayed losslessly in another. Replay never re-discovers or re-resolves anything; instead it re-verifies the
interpreter and the seed artifacts against the recorded fingerprints and refuses to create when either has drifted.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from itertools import starmap
from pathlib import Path
from typing import TYPE_CHECKING

from python_discovery import PythonInfo

from virtualenv.app_data import make_app_data
from virtualenv.config.cli.parser import VirtualEnvConfigParser, VirtualEnvOptions
from virtualenv.run.plugin.activators import ActivationSelector
from virtualenv.run.plugin.creators import CreatorSelector
from virtualenv.run.plugin.seeders import SeederSelector
from virtualenv.run.session import Session
from virtualenv.seed.wheels.util import Wheel
from virtualenv.version import __version__

if TYPE_CHECKING:
    from collections.abc import Mapping

    from virtualenv.activation.activator import Activator
    from virtualenv.create.creator import Creator
    from virtualenv.seed.seeder import Seeder

LOGGER = logging.getLogger(__name__)

#: version of the on-disk specification format; bump whenever the layout below changes in a non-backwards compatible
#: way, so that an older virtualenv rejects a newer spec instead of misinterpreting it
SPEC_VERSION = 1

#: option namespace attributes that are runtime objects, re-derived during replay, or describe the export operation
#: itself rather than the environment to create
_OPTION_SKIP = {
    "app_data",
    "env",
    "meta",
    "describe",
    "_src",
    "py_version",
    "export_spec",
    "from_spec",
    # logging controls do not describe the environment; the count actions accumulate across the parser's repeated
    # parse passes, so recording the values would make a replayed run suppress its own error reporting
    "verbose",
    "quiet",
}

#: interpreter attributes that uniquely identify the interpreter a specification was resolved against
_IDENTITY_FIELDS = (
    "implementation",
    "version_info",
    "architecture",
    "machine",
    "free_threaded",
    "debug_build",
    "platform",
    "os",
    "sysconfig_platform",
)


class SpecError(ValueError):
    """A creation specification cannot be loaded (missing file, malformed JSON or unsupported format version)."""


class SpecDriftError(RuntimeError):
    """A creation specification cannot be replayed because the interpreter or a seed artifact has drifted."""


def _as_mapping(value: object, where: str) -> Mapping[str, object]:
    """Return ``value`` as a mapping, raising :class:`SpecError` when a loaded spec has the wrong shape."""
    if not isinstance(value, dict):
        msg = f"invalid creation spec: {where} must be a JSON object"
        raise SpecError(msg)
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_executable(system_executable: str | None) -> str | None:
    """SHA-256 of the resolved interpreter binary, best effort.

    Returns ``None`` when the binary cannot be hashed (gone, unreadable); the interpreter identity fingerprint is still
    enforced independently, so a missing hash weakens but does not disable verification.
    """
    if not system_executable:
        return None
    try:
        target = os.path.realpath(system_executable)
        if os.path.isfile(target):
            return _sha256(Path(target))
    except OSError:
        return None
    return None


def _interpreter_identity(interpreter: PythonInfo) -> dict[str, object]:
    return {
        field: (list(getattr(interpreter, field)) if field == "version_info" else getattr(interpreter, field))
        for field in _IDENTITY_FIELDS
    }


def _to_jsonable(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


class CreationSpec:
    """A resolved creation specification that can be serialized to JSON and replayed deterministically."""

    def __init__(self, data: Mapping[str, object]) -> None:
        self._data = dict(data)

    # -- capture / serialize -------------------------------------------------

    @classmethod
    def capture(cls, session: Session, options: VirtualEnvOptions) -> CreationSpec:
        """Capture a specification from a resolved (but not yet run) session and its parsed options.

        Resolving the seed artifacts may populate the app-data cache exactly like a real run would, but never touches
        the destination environment.
        """
        interpreter = session.interpreter
        wheel_records = []
        if session.seeder is not None and getattr(session.seeder, "enabled", False):
            artifacts = session.seeder.resolve_artifacts(session.creator)
            if artifacts:
                wheel_records = list(starmap(_seed_record, sorted(artifacts.items())))

        data = {
            "spec_version": SPEC_VERSION,
            "virtualenv_version": __version__,
            "creator": {"key": options.creator, "type": type(session.creator).__name__},
            "seeder": {
                "key": options.seeder,
                "type": type(session.seeder).__name__,
                "enabled": bool(session.seeder.enabled),
            },
            "activators": _activator_records(session.activators),
            "interpreter": {
                "identity": _interpreter_identity(interpreter),
                "system_executable": interpreter.system_executable,
                "executable_sha256": _hash_executable(interpreter.system_executable),
                # the full collected interpreter info lets replay rebuild an identical PythonInfo without probing
                "info": interpreter.to_dict(),
            },
            "seeds": {"wheels": wheel_records},
            "options": {
                key: _to_jsonable(value)
                for key, value in vars(options).items()
                if key not in _OPTION_SKIP and not key.startswith("_")
            },
            "option_sources": {
                key: _to_jsonable(value)
                for key, value in vars(options).get("_sources", {}).items()
                if key not in _OPTION_SKIP and not key.startswith("_")
            },
        }
        return cls(data)

    def to_dict(self) -> dict[str, object]:
        return dict(self._data)

    def dump_json(self) -> str:
        """Serialize the specification to deterministic JSON (sorted keys, fixed indentation)."""
        return json.dumps(self._data, indent=2, sort_keys=True)

    def save(self, path: os.PathLike[str] | str) -> Path:
        target = Path(path)
        if target.parent and not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{self.dump_json()}\n", encoding="utf-8")
        return target

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> CreationSpec:
        spec = cls(data)
        spec.validate()
        return spec

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> CreationSpec:
        target = Path(path)
        try:
            raw = target.read_text(encoding="utf-8")
        except OSError as exception:
            msg = f"cannot read creation spec {target}: {exception}"
            raise SpecError(msg) from exception
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exception:
            msg = f"creation spec {target} is not valid JSON: {exception}"
            raise SpecError(msg) from exception
        if not isinstance(data, dict):
            msg = f"creation spec {target} must contain a JSON object"
            raise SpecError(msg)
        return cls.from_dict(data)

    def validate(self) -> None:
        """Reject specifications this virtualenv does not know how to replay."""
        version = self._data.get("spec_version")
        if version != SPEC_VERSION:
            msg = f"unsupported creation spec version {version!r}; this virtualenv supports {SPEC_VERSION}"
            raise SpecError(msg)
        for required in ("creator", "seeder", "activators", "interpreter", "seeds", "options"):
            if required not in self._data:
                msg = f"creation spec is missing required section {required!r}"
                raise SpecError(msg)
        interpreter = self._data["interpreter"]
        if not isinstance(interpreter, dict) or "identity" not in interpreter or "system_executable" not in interpreter:
            msg = "creation spec interpreter section is incomplete"
            raise SpecError(msg)

    # -- replay --------------------------------------------------------------

    def build_session(self, env: Mapping[str, str]) -> Session:
        """Verify the specification against the current machine and build an identical, ready-to-run session."""
        self.validate()
        options_data = self._data["options"]
        if not isinstance(options_data, dict):
            msg = "creation spec options section must be an object"
            raise SpecError(msg)

        app_data = make_app_data(
            None,
            read_only=bool(options_data.get("read_only_app_data", False)),
            env=dict(env),
        )
        interpreter = self._verify_interpreter(app_data, env)
        options = self._restore_options(options_data, env, app_data)

        # rebuild the very same plugins via the selectors, which also re-validates that the recorded keys are still
        # available and applicable to the (verified) interpreter - no discovery and no config lookup happens here
        parser = VirtualEnvConfigParser(options, dict(env))
        elements = [
            CreatorSelector(interpreter, parser),
            SeederSelector(interpreter, parser),
            ActivationSelector(interpreter, parser),
        ]
        for element in elements:
            element.handle_selected_arg_parse(options)
        creator, seeder, activators = (element.create(options) for element in elements)

        self._verify_components(creator, seeder, activators)
        self._pin_seeds(seeder)
        options.py_version = interpreter.version_info  # ty: ignore[attr-defined]
        return Session(options.verbosity, app_data, interpreter, creator, seeder, activators)  # ty: ignore[arg-type]

    def _restore_options(
        self,
        options_data: Mapping[str, object],
        env: Mapping[str, str],
        app_data: object,
    ) -> VirtualEnvOptions:
        options = VirtualEnvOptions()
        for key, raw_value in options_data.items():
            value = [Path(item) for item in raw_value] if key == "extra_search_dir" else raw_value
            setattr(options, key, value)
        options.env = dict(env)  # type: ignore[attr-defined]
        options.app_data = app_data  # type: ignore[attr-defined]
        # provenance drives --symlinks/--copies precedence resolution in the creator
        sources = self._data.get("option_sources")
        if isinstance(sources, dict):
            options._sources.update(sources)  # ruff:ignore[private-member-access]  # ty: ignore[attr-defined]
        return options

    def _verify_interpreter(self, app_data: object, env: Mapping[str, str]) -> PythonInfo:
        record = _as_mapping(self._data["interpreter"], "interpreter")
        expected = record["identity"]
        system_executable = record.get("system_executable")
        resolved = os.path.realpath(system_executable) if system_executable else ""
        if not system_executable or not os.path.exists(resolved):
            msg = (
                f"refusing to create from spec: interpreter {system_executable!r} is no longer available; "
                f"re-export the creation spec against the current interpreter"
            )
            raise SpecDriftError(msg)

        live = PythonInfo.from_exe(
            system_executable,
            app_data,  # type: ignore[arg-type]
            resolve_to_host=True,
            raise_on_error=False,
            env=dict(env),
        )
        if live is None:
            msg = f"refusing to create from spec: cannot interrogate interpreter {system_executable!r} anymore"
            raise SpecDriftError(msg)

        actual = _interpreter_identity(live)
        if actual != expected:
            differing = ", ".join(
                f"{field}: {expected[field]!r} -> {actual.get(field)!r}"  # type: ignore[index]
                for field in expected  # type: ignore[union-attr]
                if actual.get(field) != expected[field]  # type: ignore[index]
            )
            msg = (
                f"interpreter drift for {system_executable} ({differing}); re-export the creation spec if the new "
                f"interpreter is intended"
            )
            raise SpecDriftError(msg)

        expected_hash = record.get("executable_sha256")
        if expected_hash:
            actual_hash = _hash_executable(system_executable)
            if actual_hash != expected_hash:
                msg = (
                    f"interpreter executable sha256 mismatch for {system_executable}: expected {expected_hash}, "
                    f"got {actual_hash}"
                )
                raise SpecDriftError(msg)
        return live

    def _verify_components(self, creator: Creator, seeder: Seeder, activators: list[Activator]) -> None:
        creator_record = _as_mapping(self._data["creator"], "creator")
        if type(creator).__name__ != creator_record.get("type"):
            msg = (
                f"creator plugin drift: spec was resolved with {creator_record.get('type')!r}, but key "
                f"{creator_record.get('key')!r} now selects {type(creator).__name__!r}"
            )
            raise SpecDriftError(msg)

        seeder_record = _as_mapping(self._data["seeder"], "seeder")
        if type(seeder).__name__ != seeder_record.get("type") or bool(seeder.enabled) != bool(
            seeder_record.get("enabled")
        ):
            msg = (
                f"seeder plugin drift: spec was resolved with {seeder_record.get('type')!r} "
                f"(enabled={seeder_record.get('enabled')}), now {type(seeder).__name__!r} (enabled={seeder.enabled})"
            )
            raise SpecDriftError(msg)

        expected_activators = [entry.get("type") for entry in self._data.get("activators", [])]  # type: ignore[union-attr]
        actual_activators = [type(activator).__name__ for activator in activators]
        if actual_activators != expected_activators:
            msg = f"activator plugin drift: spec expected {expected_activators}, resolved {actual_activators}"
            raise SpecDriftError(msg)

    def _pin_seeds(self, seeder: Seeder) -> None:
        seeds = _as_mapping(self._data["seeds"], "seeds")
        records = seeds.get("wheels", [])
        if not records:
            return
        pinned = self._verified_wheels(records)  # type: ignore[arg-type]
        seeder.pin_artifacts(pinned)

    @staticmethod
    def _verified_wheels(records: list[Mapping[str, str]]) -> dict[str, Wheel]:
        pinned: dict[str, Wheel] = {}
        for record in records:
            distribution = record["distribution"]
            path = Path(record["path"])
            if not path.is_file():
                msg = (
                    f"seed artifact drift: {distribution} {record.get('filename')} recorded at {path} is missing; "
                    f"re-export the creation spec to pin the current artifacts"
                )
                raise SpecDriftError(msg)
            actual_hash = _sha256(path)
            if actual_hash != record.get("sha256"):
                msg = (
                    f"seed artifact drift: sha256 mismatch for {distribution} {record.get('filename')}: expected "
                    f"{record.get('sha256')}, got {actual_hash}"
                )
                raise SpecDriftError(msg)
            wheel = Wheel.from_path(path)
            if (
                wheel is None
                or wheel.distribution != distribution
                or wheel.version != record.get("version")
                or wheel.name != record.get("filename")
            ):
                msg = f"seed artifact drift: file at {path} is no longer {distribution} {record.get('version')}"
                raise SpecDriftError(msg)
            pinned[distribution] = wheel
        return pinned


def _seed_record(distribution: str, wheel: Wheel) -> dict[str, str]:
    return {
        "distribution": distribution,
        "version": wheel.version,
        "filename": wheel.name,
        "path": str(wheel.path),
        "sha256": _sha256(wheel.path),
    }


def _activator_records(activators: list[Activator]) -> list[dict[str, str | None]]:
    # map the concrete activator classes back to the entry point key they were selected with, when known
    key_for_type = {
        activator_class: key for key, activator_class in ActivationSelector.options("virtualenv.activate").items()
    }
    return [{"key": key_for_type.get(type(activator)), "type": type(activator).__name__} for activator in activators]


__all__ = [
    "SPEC_VERSION",
    "CreationSpec",
    "SpecDriftError",
    "SpecError",
]
