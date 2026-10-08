from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import ArgumentParser
    from collections.abc import Mapping

    from python_discovery import PythonInfo

    from virtualenv.app_data.base import AppData
    from virtualenv.config.cli.parser import VirtualEnvOptions
    from virtualenv.create.creator import Creator
    from virtualenv.seed.wheels.util import Wheel


class Seeder(ABC):
    """A seeder will install some seed packages into a virtual environment."""

    def __init__(self, options: VirtualEnvOptions, enabled: bool) -> None:
        """Create.

        :param options: the parsed options as defined within :meth:`add_parser_arguments`
        :param enabled: a flag weather the seeder is enabled or not

        """
        self.enabled = enabled
        self.env = options.env

    @classmethod
    def cannot_seed(cls, interpreter: PythonInfo) -> str | None:  # ruff:ignore[unused-class-method-argument]
        """Explain why this seeder cannot install seed packages for the given interpreter.

        :param interpreter: the interpreter the environment is based on

        :returns: ``None`` when the seeder supports the interpreter, otherwise a message describing why it cannot;
            selection rejects a seeder that returns a message and surfaces it to the user

        """
        return None

    @classmethod
    def add_parser_arguments(cls, parser: ArgumentParser, interpreter: PythonInfo, app_data: AppData) -> None:
        """Add CLI arguments for this seed mechanisms.

        :param parser: the CLI parser
        :param app_data: the CLI parser
        :param interpreter: the interpreter this virtual environment is based of

        """
        raise NotImplementedError

    @abstractmethod
    def run(self, creator: Creator) -> None:
        """Perform the seed operation.

        :param creator: the creator (based of :class:`virtualenv.create.creator.Creator`) we used to create this virtual
            environment

        """
        raise NotImplementedError

    def resolve_artifacts(self, creator: Creator) -> Mapping[str, Wheel] | None:  # ruff:ignore[unused-method-argument]
        """Resolve the concrete seed artifacts this seeder would install, without installing them.

        Used when exporting a creation specification so that the resolved wheels (distribution -> wheel) can be
        recorded and pinned for a later, lossless replay.

        :param creator: the creator used to describe the virtual environment

        :returns: a mapping of distribution name to the resolved :class:`~virtualenv.seed.wheels.util.Wheel`, or
            ``None`` when the seeder does not install pinable file artifacts (and therefore cannot be replayed
            deterministically)

        """
        return None

    def pin_artifacts(self, artifacts: Mapping[str, Wheel]) -> None:
        """Pin this seeder to install exactly the given, already verified seed artifacts.

        Once pinned the seeder must not re-discover, periodically update or download anything during :meth:`run`, so
        that replaying a creation specification produces the same environment regardless of later package releases.

        :param artifacts: the mapping of distribution name to wheel as previously returned by :meth:`resolve_artifacts`

        """
        # seeders without pinable file artifacts ignore the pin; concrete seeders override this method
        _ = artifacts


__all__ = [
    "Seeder",
]
