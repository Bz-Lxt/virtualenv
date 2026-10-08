from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from threading import Thread

import pytest

from virtualenv.events import (
    SCHEMA_VERSION,
    Event,
    EventStream,
    SeedTaskFailed,
    SeedTaskInstallCompleted,
    SeedTaskInstallStarted,
    SeedTaskStarted,
    SeedTaskWheelAcquired,
    SessionFailed,
    SessionInterrupted,
    SessionStarted,
    SessionSucceeded,
    StageCompleted,
    StageStarted,
)
from virtualenv.run.session import Session


def test_publish_assigns_gapless_monotonic_sequence() -> None:
    stream = EventStream()
    stream.publish(StageStarted(stage="create"))
    stream.publish(StageCompleted(stage="create"))
    stream.publish(SessionSucceeded())

    assert [event.seq for event in stream.events()] == [1, 2, 3]
    assert all(event.timestamp > 0 for event in stream.events())


def test_subscribe_receives_live_events() -> None:
    stream = EventStream()
    received: list[Event] = []
    stream.subscribe(received.append)

    event = StageStarted(stage="seed")
    assert stream.publish(event) is True

    assert len(received) == 1
    assert received[0].type == "stage.started"
    assert received[0].seq == 1


def test_subscribe_replays_backlog() -> None:
    stream = EventStream()
    stream.publish(SessionStarted(dest="env"))
    stream.publish(StageStarted(stage="create"))

    received: list[Event] = []
    stream.subscribe(received.append)

    assert [event.seq for event in received] == [1, 2]
    stream.publish(StageCompleted(stage="create"))
    assert [event.seq for event in received] == [1, 2, 3]


def test_subscribe_without_replay_only_gets_live_events() -> None:
    stream = EventStream()
    stream.publish(SessionStarted(dest="env"))

    received: list[Event] = []
    stream.subscribe(received.append, replay=False)
    assert not received

    stream.publish(StageStarted(stage="create"))
    assert len(received) == 1


def test_unsubscribe_stops_delivery() -> None:
    stream = EventStream()
    received: list[Event] = []
    subscription = stream.subscribe(received.append)

    stream.publish(StageStarted(stage="create"))
    subscription.unsubscribe()
    subscription.unsubscribe()  # idempotent
    stream.publish(StageCompleted(stage="create"))

    assert len(received) == 1


def test_subscription_context_manager() -> None:
    stream = EventStream()
    received: list[Event] = []
    with stream.subscribe(received.append):
        stream.publish(StageStarted(stage="create"))
    stream.publish(StageCompleted(stage="create"))

    assert len(received) == 1


def test_close_rejects_late_events() -> None:
    stream = EventStream()
    received: list[Event] = []
    stream.subscribe(received.append)
    stream.publish(StageStarted(stage="create"))

    stream.close()
    stream.close()  # idempotent
    assert stream.closed

    assert stream.publish(StageCompleted(stage="create")) is False
    assert not received[1:]
    assert stream.dropped == 1


def test_terminal_event_is_unique_and_always_last() -> None:
    stream = EventStream()
    stream.publish(StageStarted(stage="create"))

    assert stream.publish(SessionSucceeded(result={"dest": "env"})) is True
    # no event - terminal or not - can follow a delivered terminal
    assert stream.publish(StageCompleted(stage="create")) is False
    assert stream.publish(SessionFailed(error_type="x", error_message="y")) is False

    terminal = stream.terminal_event()
    assert isinstance(terminal, SessionSucceeded)
    assert stream.is_terminated
    assert stream.events()[-1] is terminal


def test_listener_exception_is_isolated(caplog) -> None:
    stream = EventStream()

    def broken(_event: Event) -> None:
        msg = "listener boom"
        raise RuntimeError(msg)

    healthy: list[Event] = []
    stream.subscribe(broken)
    stream.subscribe(healthy.append)

    with caplog.at_level(logging.ERROR):
        stream.publish(StageStarted(stage="create"))

    assert len(healthy) == 1
    assert "listener boom" in caplog.text


def test_concurrent_publish_keeps_total_order() -> None:
    stream = EventStream()
    per_thread = 50
    thread_count = 8
    received: list[Event] = []
    stream.subscribe(received.append)

    def _publish_many() -> None:
        for _idx in range(per_thread):
            stream.publish(StageStarted(stage="seed"))

    threads = [Thread(target=_publish_many) for _ in range(thread_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    total = per_thread * thread_count
    assert [event.seq for event in received] == list(range(1, total + 1))


@pytest.mark.parametrize(
    ("event", "expected_type"),
    [
        (SessionStarted(dest="env", interpreter="3.13", virtualenv_version="1"), "session.started"),
        (StageStarted(stage="create"), "stage.started"),
        (StageCompleted(stage="create", result={"ok": 1}), "stage.completed"),
        (SeedTaskStarted(distribution="pip", requested_version="bundle"), "seed.task_started"),
        (SeedTaskWheelAcquired(distribution="pip", version="26", path="/w"), "seed.task_wheel_acquired"),
        (SeedTaskInstallStarted(distribution="pip", path="/w"), "seed.task_install_started"),
        (SeedTaskInstallCompleted(distribution="pip", path="/w"), "seed.task_install_completed"),
        (SeedTaskFailed(distribution="pip", error_type="E", error_message="m"), "seed.task_failed"),
        (SessionSucceeded(), "session.succeeded"),
        (SessionFailed(error_type="E", error_message="m"), "session.failed"),
        (SessionInterrupted(reason="keyboard-interrupt"), "session.interrupted"),
    ],
)
def test_event_payload_is_json_serializable(event: Event, expected_type: str) -> None:
    as_dict = event.to_dict()
    assert as_dict["type"] == expected_type
    assert as_dict["schema_version"] == SCHEMA_VERSION
    json.dumps(as_dict)  # all payloads must be JSON friendly


# ---------------------------------------------------------------------------
# Session lifecycle integration with lightweight fakes
# ---------------------------------------------------------------------------


@dataclass
class _FakeInterpreter:
    version_release_str: str = "3.13"


class _FakePyEnvCfg:
    def __init__(self) -> None:
        self.written = False

    def write(self) -> None:
        self.written = True


class _FakeCreator:
    def __init__(self) -> None:
        self.dest = "env"
        self.pyenv_cfg = _FakePyEnvCfg()
        self.ran = False
        self.debug: dict = {}

    def run(self) -> None:
        self.ran = True


class _FakeSeeder:
    def __init__(self, enabled: bool = False, fail: bool = False) -> None:
        self.enabled = enabled
        self._fail = fail
        self.ran = False

    def run(self, _creator: object) -> None:
        if self._fail:
            msg = "seed boom"
            raise RuntimeError(msg)
        self.ran = True


class _FakeActivator:
    def __init__(self) -> None:
        self.generated = False

    def generate(self, _creator: object) -> None:
        self.generated = True


class _FakeAppData:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _make_session(*, seeder: object | None = None, activators: list | None = None) -> tuple[Session, _FakeAppData]:
    app_data = _FakeAppData()
    session = Session(
        verbosity=3,
        app_data=app_data,
        interpreter=_FakeInterpreter(),
        creator=_FakeCreator(),
        seeder=seeder if seeder is not None else _FakeSeeder(),
        activators=activators or [],
    )
    return session, app_data


def test_session_success_reports_every_stage_and_closes_stream() -> None:
    seeder = _FakeSeeder(enabled=True)
    activator = _FakeActivator()
    session, app_data = _make_session(seeder=seeder, activators=[activator])
    received: list[Event] = []
    session.events.subscribe(received.append)

    with session:
        session.run()

    assert isinstance(received[0], SessionStarted)
    stage_pairs = [(event.stage, type(event).__name__) for event in received[1:-1]]
    assert ("create", "StageStarted") in stage_pairs
    assert ("create", "StageCompleted") in stage_pairs
    assert ("seed", "StageCompleted") in stage_pairs
    assert ("activate", "StageCompleted") in stage_pairs

    terminal = received[-1]
    assert isinstance(terminal, SessionSucceeded)
    assert sum(isinstance(event, SessionSucceeded | SessionFailed | SessionInterrupted) for event in received) == 1
    assert seeder.ran
    assert activator.generated
    assert session.creator.pyenv_cfg.written

    # resources down and the stream rejects late events
    assert app_data.closed
    assert session.events.closed
    assert session.events.publish(StageStarted(stage="create")) is False


def test_session_disabled_seeder_reports_skipped_stage() -> None:
    session, _app_data = _make_session()
    with session:
        session.run()

    seed_events = [
        event for event in session.events.events() if isinstance(event, StageCompleted) and event.stage == "seed"
    ]
    assert seed_events
    assert seed_events[0].result == {"seeder": "_FakeSeeder", "skipped": True}


def test_session_failure_emits_single_failed_terminal_and_still_closes() -> None:
    class _FailingCreator(_FakeCreator):
        def run(self) -> None:
            msg = "create boom"
            raise RuntimeError(msg)

    app_data = _FakeAppData()
    session = Session(3, app_data, _FakeInterpreter(), _FailingCreator(), _FakeSeeder(), [])

    with pytest.raises(RuntimeError, match="create boom"), session:
        session.run()

    events = session.events.events()
    assert isinstance(events[0], SessionStarted)
    assert isinstance(events[1], StageStarted)
    terminal = events[-1]
    assert isinstance(terminal, SessionFailed)
    assert terminal.error_type == "RuntimeError"
    assert "create boom" in terminal.error_message
    assert terminal.traceback is not None
    assert "Traceback" in terminal.traceback
    assert len([event for event in events if event.is_terminal]) == 1
    assert app_data.closed
    assert session.events.closed


def test_session_seed_failure_fails_on_seed_stage() -> None:
    session, _app_data = _make_session(seeder=_FakeSeeder(enabled=True, fail=True))

    with pytest.raises(RuntimeError, match="seed boom"), session:
        session.run()

    terminal = session.events.terminal_event()
    assert isinstance(terminal, SessionFailed)
    started_stages = [event.stage for event in session.events.events() if isinstance(event, StageStarted)]
    assert started_stages[-1] == "seed"
    assert not [
        event for event in session.events.events() if isinstance(event, StageCompleted) and event.stage == "seed"
    ]


def test_session_keyboard_interrupt_emits_interrupted_terminal() -> None:
    class _InterruptingCreator(_FakeCreator):
        def run(self) -> None:
            raise KeyboardInterrupt

    app_data = _FakeAppData()
    session = Session(3, app_data, _FakeInterpreter(), _InterruptingCreator(), _FakeSeeder(), [])

    with pytest.raises(KeyboardInterrupt), session:
        session.run()

    terminal = session.events.terminal_event()
    assert isinstance(terminal, SessionInterrupted)
    assert terminal.reason == "keyboard-interrupt"
    assert session.events.events()[-1] is terminal
    assert app_data.closed
    assert session.events.closed
