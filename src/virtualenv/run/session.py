from __future__ import annotations

import json
import logging
import sys
from typing import TYPE_CHECKING

from virtualenv.events import (
    STAGE_ACTIVATE,
    STAGE_CREATE,
    STAGE_SEED,
    EventStream,
    SessionFailed,
    SessionInterrupted,
    SessionStarted,
    SessionSucceeded,
    StageCompleted,
    StageStarted,
    describe_exception,
    keyboard_interrupt,
)
from virtualenv.version import __version__

if TYPE_CHECKING:
    from types import TracebackType

    from python_discovery import PythonInfo

    from virtualenv.activation.activator import Activator
    from virtualenv.app_data.base import AppData
    from virtualenv.create.creator import Creator
    from virtualenv.seed.seeder import Seeder

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

LOGGER = logging.getLogger(__name__)


class Session:
    """Represents a virtual environment creation session."""

    def __init__(  # ruff:ignore[too-many-arguments]
        self,
        verbosity: int,
        app_data: AppData,
        interpreter: PythonInfo,
        creator: Creator,
        seeder: Seeder,
        activators: list[Activator],
        event_stream: EventStream | None = None,
    ) -> None:
        self._verbosity = verbosity
        self._app_data = app_data
        self._interpreter = interpreter
        self._creator = creator
        self._seeder = seeder
        self._activators = activators
        self._events = EventStream() if event_stream is None else event_stream
        # make sure every component that can publish (seed workers) uses this single stream
        if seeder is not None:
            seeder.event_stream = self._events

    @property
    def verbosity(self) -> int:
        """The verbosity of the run."""
        return self._verbosity

    @property
    def interpreter(self) -> PythonInfo:
        """Create a virtual environment based on this reference interpreter."""
        return self._interpreter

    @property
    def creator(self) -> Creator:
        """The creator used to build the virtual environment (must be compatible with the interpreter)."""
        return self._creator

    @property
    def seeder(self) -> Seeder:
        """The mechanism used to provide the seed packages (pip, setuptools, wheel)."""
        return self._seeder

    @property
    def activators(self) -> list[Activator]:
        """Activators used to generate activations scripts."""
        return self._activators

    @property
    def events(self) -> EventStream:
        """Structured event stream of the creation; subscribe before calling :meth:`run`."""
        return self._events

    def run(self) -> None:
        self._events.publish(
            SessionStarted(
                dest=str(self.creator.dest),
                interpreter=self.interpreter.version_release_str,
                virtualenv_version=__version__,
            ),
        )
        try:
            self._create()
            self._seed()
            self._activate()
            self.creator.pyenv_cfg.write()
        except KeyboardInterrupt as exception:
            self._events.publish(self._interrupted(exception))
            raise
        except Exception as exception:
            self._events.publish(self._failed(exception))
            raise
        else:
            self._events.publish(SessionSucceeded(result={"dest": str(self.creator.dest)}))

    def _create(self) -> None:
        self._events.publish(StageStarted(stage=STAGE_CREATE))
        LOGGER.info("create virtual environment via %s", self.creator)
        self.creator.run()
        LOGGER.debug(_DEBUG_MARKER)
        LOGGER.debug("%s", _Debug(self.creator))
        self._events.publish(
            StageCompleted(
                stage=STAGE_CREATE,
                result={"creator": type(self.creator).__name__, "dest": str(self.creator.dest)},
            ),
        )

    def _seed(self) -> None:
        if self.seeder is not None and self.seeder.enabled:
            self._events.publish(StageStarted(stage=STAGE_SEED))
            LOGGER.info("add seed packages via %s", self.seeder)
            self.seeder.run(self.creator)
            self._events.publish(
                StageCompleted(
                    stage=STAGE_SEED,
                    result={"seeder": type(self.seeder).__name__, "enabled": True},
                ),
            )
        else:
            self._events.publish(StageStarted(stage=STAGE_SEED))
            self._events.publish(
                StageCompleted(
                    stage=STAGE_SEED,
                    result={"seeder": type(self.seeder).__name__ if self.seeder is not None else None, "skipped": True},
                ),
            )

    def _activate(self) -> None:
        if self.activators:
            self._events.publish(StageStarted(stage=STAGE_ACTIVATE))
            active = ", ".join(type(i).__name__.replace("Activator", "") for i in self.activators)
            LOGGER.info("add activators for %s", active)
            for activator in self.activators:
                activator.generate(self.creator)
            self._events.publish(
                StageCompleted(
                    stage=STAGE_ACTIVATE,
                    result={"activators": [type(i).__name__ for i in self.activators]},
                ),
            )
        else:
            self._events.publish(StageStarted(stage=STAGE_ACTIVATE))
            self._events.publish(
                StageCompleted(stage=STAGE_ACTIVATE, result={"activators": [], "skipped": True}),
            )

    @staticmethod
    def _failed(exception: Exception) -> SessionFailed:
        details = describe_exception(exception)
        return SessionFailed(
            error_type=str(details["error_type"]),
            error_message=str(details["error_message"]),
            traceback=details["traceback"],
        )

    @staticmethod
    def _interrupted(exception: KeyboardInterrupt) -> SessionInterrupted:
        return keyboard_interrupt(exception)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._app_data.close()
        # close the stream only after resources are down; afterwards publishes are rejected
        self._events.close()


_DEBUG_MARKER = "=" * 30 + " target debug " + "=" * 30


class _Debug:
    """lazily populate debug."""

    def __init__(self, creator: Creator) -> None:
        self.creator = creator

    def __repr__(self) -> str:
        return json.dumps(self.creator.debug, indent=2)


__all__ = [
    "Session",
]
