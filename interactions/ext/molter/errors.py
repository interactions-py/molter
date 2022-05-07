import typing

from .utils import escape_mentions

if typing.TYPE_CHECKING:
    from .context import MolterContext


__all__ = ("MolterException", "BadArgument", "CheckFailure")


class MolterException(Exception):
    pass


class BadArgument(MolterException):
    """A special exception for invalid arguments when using molter commands."""

    def __init__(self, message: typing.Optional[str] = None, *args: typing.Any) -> None:
        if message is not None:
            message = escape_mentions(message)
            super().__init__(message, *args)
        else:
            super().__init__(*args)


class CheckFailure(MolterException):
    """
    An exception when a check fails.

    Attributes:
        context (`MolterContext`): The context for this check.
        check (`Callable[[MolterContext], typing.Coroutine[Any, Any, bool]]`): The check that failed.
        message: (`str`, optional): The error message.
    """

    def __init__(
        self,
        context: "MolterContext",
        check: typing.Callable[
            ["MolterContext"], typing.Coroutine[typing.Any, typing.Any, bool]
        ],
        message: typing.Optional[str] = "A check has failed.",
    ):
        self.context = context
        self.check = check

        super().__init__(message)
