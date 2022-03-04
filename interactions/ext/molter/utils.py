import inspect
import re
import typing

import interactions

__all__ = (
    "SnowflakeType",
    "OptionalSnowflakeType",
    "when_mentioned",
    "when_mentioned_or",
    "maybe_coroutine",
    "ARG_PARSE_REGEX",
    "INITIAL_WORD_REGEX",
    "MENTION_REGEX",
    "get_args",
    "get_first_word",
    "escape_mentions",
    "Singleton",
    "Sentinel",
    "MISSING",
)

# most of these come from dis-snek
# thanks, polls!

SnowflakeType = typing.Union[interactions.Snowflake, int, str]
OptionalSnowflakeType = typing.Optional[SnowflakeType]


async def when_mentioned(bot: interactions.Client, _):
    return [f"<@{bot.me.id}> ", f"<@!{bot.me.id}> "]  # type: ignore


async def when_mentioned_or(*prefixes: str):
    async def new_mention(bot: interactions.Client, _):
        return await when_mentioned(bot, _) + list(prefixes)

    return new_mention


async def maybe_coroutine(func: typing.Callable, *args, **kwargs):
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    else:
        return func(*args, **kwargs)


_quotes = {
    '"': '"',
    "‘": "’",
    "‚": "‛",
    "“": "”",
    "„": "‟",
    "⹂": "⹂",
    "「": "」",
    "『": "』",
    "〝": "〞",
    "﹁": "﹂",
    "﹃": "﹄",
    "＂": "＂",
    "｢": "｣",
    "«": "»",
    "‹": "›",
    "《": "》",
    "〈": "〉",
}
_start_quotes = frozenset(_quotes.keys())

_pending_regex = r"(1.*2|[^\s]+)"
_pending_regex = _pending_regex.replace("1", f"[{''.join(list(_quotes.keys()))}]")
_pending_regex = _pending_regex.replace("2", f"[{''.join(list(_quotes.values()))}]")

ARG_PARSE_REGEX = re.compile(_pending_regex)
INITIAL_WORD_REGEX = re.compile(r"^([^\s]+)\s*?")

MENTION_REGEX = re.compile(r"@(everyone|here|[!&]?[0-9]{17,20})")


def get_args(text: str) -> list:
    """
    Get arguments from an input text.
    Args:
        text: The text to process
    Returns:
        A list of words
    """
    args = ARG_PARSE_REGEX.findall(text)
    return [(arg[1:-1] if arg[0] in _start_quotes else arg) for arg in args]


def get_first_word(text: str) -> typing.Optional[str]:
    """
    Get a the first word in a string, regardless of whitespace type.
    Args:
        text: The text to process
    Returns:
         The requested word
    """
    found = INITIAL_WORD_REGEX.findall(text)
    if len(found) == 0:
        return None
    return found[0]


def escape_mentions(content: str) -> str:
    """
    Escape mentions that could ping someone in a string.
    note:
        This does not escape channel mentions as they do not ping anybody.
    Args:
        content: The string to escape
    Returns:
        Processed string
    """
    return MENTION_REGEX.sub("@\u200b\\1", content)


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Sentinel(metaclass=Singleton):
    @staticmethod
    def _get_caller_module() -> str:
        stack = inspect.stack()

        caller = stack[2][0]
        return caller.f_globals.get("__name__")

    def __init__(self):
        self.__module__ = self._get_caller_module()
        self.name = type(self).__name__

    def __repr__(self):
        return self.name

    def __reduce__(self):
        return self.name

    def __copy__(self):
        return self

    def __deepcopy__(self, _):
        return self


class Missing(Sentinel):
    # inter.py's MISSING isn't actually a sentinel
    # id rather not rely on it, and since Sentinel
    # is needed anyways, might as well have it here
    def __getattr__(self, *_):
        return None

    def __bool__(self):
        return False


MISSING = Missing()
