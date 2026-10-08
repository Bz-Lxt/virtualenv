"""Structured, subscribable event stream for virtual environment creation.

Programmatic consumers historically had to scrape text log output to follow a creation, and the seed
stage runs installer threads concurrently so those log lines could arrive interleaved or out of order.
This module provides a stable alternative:

* :class:`Event` payloads are typed, immutable and serializable; new event types may be added in any
  release and consumers are expected to ignore event types and fields they do not understand. Breaking
  payload changes bump :data:`SCHEMA_VERSION`.
* :class:`EventStream` assigns a single monotonic :attr:`Event.seq` to every event under a lock, giving
  subscribers a total order even when events are published from parallel worker threads.
* Exactly one terminal event (:class:`SessionSucceeded`, :class:`SessionFailed` or
  :class:`SessionInterrupted`) is ever delivered, and it is always the last event.
* Once the stream (or its owning session) is closed, further publishes are rejected silently, so no late
  event can reach a subscriber after the resources it describes were shut down.
"""

from __future__ import annotations

import contextlib
import logging
import sys
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field, fields, replace
from threading import RLock
from typing import Any, ClassVar

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

LOGGER = logging.getLogger(__name__)

#: version of the event payload contract; bumped only on breaking payload changes
SCHEMA_VERSION = 1

#: well-known creation stage names, in execution order
STAGE_CREATE = "create"
STAGE_SEED = "seed"
STAGE_ACTIVATE = "activate"

_INTERRUPT_KEYBOARD = "keyboard-interrupt"


@dataclass(frozen=True)
class Event:
    """Base class of every stream event.

    Ordering metadata is assigned by the stream at publication time, not by the publisher.
    """

    seq: int = field(default=0)
    timestamp: float = field(default=0.0)

    #: stable identifier of the event kind (used by subscribers to switch on)
    type: ClassVar[str] = "event"
    #: ``True`` for the single event that ends a session; no event is delivered after a terminal one
    is_terminal: ClassVar[bool] = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation including :attr:`type` and :data:`SCHEMA_VERSION`."""
        result = {f.name: getattr(self, f.name) for f in fields(self)}
        result["type"] = self.type
        result["schema_version"] = SCHEMA_VERSION
        return result


@dataclass(frozen=True)
class SessionStarted(Event):
    """Emitted once, before any stage runs."""

    type: ClassVar[str] = "session.started"

    dest: str | None = None
    interpreter: str | None = None
    virtualenv_version: str | None = None


@dataclass(frozen=True)
class StageStarted(Event):
    """Emitted when a creation stage begins."""

    type: ClassVar[str] = "stage.started"

    stage: str = ""


@dataclass(frozen=True)
class StageCompleted(Event):
    """Emitted when a creation stage finishes; ``result`` carries a JSON-friendly stage summary.

    When a stage fails this event is not emitted for it; the preceding :class:`StageStarted` identifies
    the in-progress stage from the terminal failure.
    """

    type: ClassVar[str] = "stage.completed"

    stage: str = ""
    result: dict[str, Any] | None = None


@dataclass(frozen=True)
class SeedTaskStarted(Event):
    """Emitted when work on one seed distribution (pip, setuptools, ...) begins."""

    type: ClassVar[str] = "seed.task_started"

    distribution: str = ""
    requested_version: str | None = None


@dataclass(frozen=True)
class SeedTaskWheelAcquired(Event):
    """Emitted once the wheel for a seed distribution was located or downloaded."""

    type: ClassVar[str] = "seed.task_wheel_acquired"

    distribution: str = ""
    version: str | None = None
    path: str | None = None


@dataclass(frozen=True)
class SeedTaskInstallStarted(Event):
    """Emitted before the wheel image is installed for a distribution (may run on a worker thread)."""

    type: ClassVar[str] = "seed.task_install_started"

    distribution: str = ""
    path: str | None = None


@dataclass(frozen=True)
class SeedTaskInstallCompleted(Event):
    """Emitted after the wheel image for a distribution was installed into the environment."""

    type: ClassVar[str] = "seed.task_install_completed"

    distribution: str = ""
    path: str | None = None


@dataclass(frozen=True)
class SeedTaskFailed(Event):
    """Emitted when acquiring or installing a seed distribution fails (may run on a worker thread)."""

    type: ClassVar[str] = "seed.task_failed"

    distribution: str = ""
    error_type: str = ""
    error_message: str = ""
    traceback: str | None = None


@dataclass(frozen=True)
class SessionSucceeded(Event):
    """Terminal event emitted once when the whole creation succeeds."""

    type: ClassVar[str] = "session.succeeded"
    is_terminal: ClassVar[bool] = True

    result: dict[str, Any] | None = None


@dataclass(frozen=True)
class SessionFailed(Event):
    """Terminal event emitted once when the creation fails with an exception."""

    type: ClassVar[str] = "session.failed"
    is_terminal: ClassVar[bool] = True

    error_type: str = ""
    error_message: str = ""
    traceback: str | None = None


@dataclass(frozen=True)
class SessionInterrupted(Event):
    """Terminal event emitted once when the creation is interrupted (e.g. Ctrl-C)."""

    type: ClassVar[str] = "session.interrupted"
    is_terminal: ClassVar[bool] = True

    reason: str = ""
    message: str | None = None


def describe_exception(exception: BaseException, *, include_traceback: bool = True) -> dict[str, str | None]:
    """Return structured failure fields for an exception.

    :param exception: the exception to describe
    :param include_traceback: include the formatted traceback

    """
    return {
        "error_type": type(exception).__name__,
        "error_message": str(exception),
        "traceback": "".join(traceback.format_exception(exception)) if include_traceback else None,
    }


EventListener = Callable[[Event], None]


class Subscription:
    """Handle for an :meth:`EventStream.subscribe` registration; supports context-manager use."""

    def __init__(self, stream: EventStream, listener: EventListener) -> None:
        self._stream = stream
        self._listener = listener

    def unsubscribe(self) -> None:
        """Stop delivering events to the subscriber (idempotent)."""
        self._stream._unsubscribe(self._listener)  # ruff:ignore[private-member-access]

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _exc_type: object, _exc_val: object, _exc_tb: object) -> None:
        self.unsubscribe()


class EventStream:
    """Thread-safe publish/subscribe bus tracking one creation session.

    Guarantees:

    * events are stamped with a gapless, strictly increasing :attr:`Event.seq` and dispatched in that
      order, regardless of the publishing thread;
    * at most one terminal event is delivered and nothing follows it;
    * after :meth:`close` no event is dispatched anymore.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._listeners: list[EventListener] = []
        self._events: list[Event] = []
        self._next = 1
        self._closed = False
        self._terminal = False
        #: number of publishes rejected because the stream was closed or already terminated
        self.dropped = 0

    @property
    def closed(self) -> bool:
        """``True`` once :meth:`close` was called."""
        return self._closed

    @property
    def is_terminated(self) -> bool:
        """``True`` once the terminal event was delivered (or the stream was closed without one)."""
        return self._terminal or self._closed

    def terminal_event(self) -> Event | None:
        """Return the delivered terminal event, if any."""
        with self._lock:
            return self._events[-1] if self._terminal else None

    def events(self) -> tuple[Event, ...]:
        """Return a snapshot of all delivered events in sequence order."""
        with self._lock:
            return tuple(self._events)

    def subscribe(self, listener: EventListener, *, replay: bool = True) -> Subscription:
        """Register ``listener``; it is called once per event with the event as the only argument.

        :param listener: a callable invoked synchronously while the stream lock is held; it must be fast
            and non-blocking. Exceptions raised by a listener are logged and isolated.
        :param replay: deliver a backlog of already published events before live events

        """
        with self._lock:
            self._listeners.append(listener)
            if replay:
                for event in self._events:
                    self._dispatch(listener, event)
        return Subscription(self, listener)

    def publish(self, event: Event) -> bool:
        """Stamp and deliver an event.

        :returns: ``True`` when delivered, ``False`` when rejected because the stream was closed or a
            terminal event was already delivered

        """
        with self._lock:
            if self._closed or self._terminal:
                self.dropped += 1
                return False
            stamped = replace(event, seq=self._next, timestamp=time.time())
            self._next += 1
            self._events.append(stamped)
            for listener in tuple(self._listeners):
                self._dispatch(listener, stamped)
            if stamped.is_terminal:
                self._terminal = True
        return True

    def close(self) -> None:
        """Shut the stream down; idempotent. No event is emitted and later publishes are rejected."""
        with self._lock:
            self._closed = True

    def _unsubscribe(self, listener: EventListener) -> None:
        with self._lock, contextlib.suppress(ValueError):
            self._listeners.remove(listener)

    @staticmethod
    def _dispatch(listener: EventListener, event: Event) -> None:
        try:
            listener(event)
        except Exception:
            LOGGER.exception("event listener %r failed on %s", listener, event.type)


def keyboard_interrupt(exception: KeyboardInterrupt) -> SessionInterrupted:
    """Build the standard terminal interruption event for a :class:`KeyboardInterrupt`."""
    message = str(exception)
    return SessionInterrupted(reason=_INTERRUPT_KEYBOARD, message=message or None)


__all__ = [
    "SCHEMA_VERSION",
    "STAGE_ACTIVATE",
    "STAGE_CREATE",
    "STAGE_SEED",
    "Event",
    "EventListener",
    "EventStream",
    "SeedTaskFailed",
    "SeedTaskInstallCompleted",
    "SeedTaskInstallStarted",
    "SeedTaskStarted",
    "SeedTaskWheelAcquired",
    "SessionFailed",
    "SessionInterrupted",
    "SessionStarted",
    "SessionSucceeded",
    "StageCompleted",
    "StageStarted",
    "Subscription",
    "describe_exception",
    "keyboard_interrupt",
]
