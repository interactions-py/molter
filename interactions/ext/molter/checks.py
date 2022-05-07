import typing

from .command import MCT
from .command import MolterCommand

if typing.TYPE_CHECKING:
    from .context import MolterContext


__all__ = ("check",)


def check(
    check: typing.Callable[
        ["MolterContext"], typing.Coroutine[typing.Any, typing.Any, bool]
    ]
) -> typing.Callable[..., MCT]:
    """
    Add a check to a command.

    Args:
        check: A coroutine as a check for this command.
    """

    def wrapper(coro: MCT) -> MCT:
        if isinstance(coro, MolterCommand):
            coro.checks.append(check)
            return coro
        if not hasattr(coro, "checks"):
            coro.__checks__ = []  # type: ignore
        coro.__checks__.append(check)  # type: ignore
        return coro

    return wrapper
