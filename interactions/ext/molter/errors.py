import typing

from .utils import escape_mentions


__all__ = ("MolterException", "BadArgument")


class MolterException(Exception):
    pass


class BadArgument(MolterException):
    def __init__(self, message: typing.Optional[str] = None, *args: typing.Any) -> None:
        if message is not None:
            message = escape_mentions(message)
            super().__init__(message, *args)
        else:
            super().__init__(*args)
