import inspect
import re
import typing

import interactions

__all__ = (
    "SnowflakeType",
    "OptionalSnowflakeType",
    "remove_prefix",
    "remove_suffix",
    "when_mentioned",
    "when_mentioned_or",
    "maybe_coroutine",
    "ARG_PARSE_REGEX",
    "MENTION_REGEX",
    "get_args_from_str",
    "get_first_word",
    "escape_mentions",
)

# most of these come from dis-snek
# thanks, polls!

SnowflakeType = typing.Union[interactions.Snowflake, int, str]
OptionalSnowflakeType = typing.Optional[SnowflakeType]


def remove_prefix(string: str, prefix: str):
    """
    Removes a prefix from a string if present.

    Args:
        string (`str`): The string to remove the prefix from.
        prefix (`str`): The prefix to remove.

    Returns:
        The string without the prefix.
    """
    return string[len(prefix) :] if string.startswith(prefix) else string[:]


def remove_suffix(string: str, suffix: str):
    """
    Removes a suffix from a string if present.

    Args:
        string (`str`): The string to remove the suffix from.
        suffix (`str`): The suffix to remove.

    Returns:
        The string without the suffix.
    """
    return string[: -len(suffix)] if string.endswith(suffix) else string[:]


async def when_mentioned(bot: interactions.Client, _):
    """
    Returns a list of the bot's mentions.

    Returns:
        A list of the bot's possible mentions.
    """
    return [f"<@{bot.me.id}> ", f"<@!{bot.me.id}> "]  # type: ignore


def when_mentioned_or(*prefixes: str):
    """
    Returns a list of the bot's mentions plus whatever prefixes are provided.

    This is intended to be used with initializing molter. If you wish to use
    it in your own function, you will need to do something similar to:

    `await when_mentioned_or(*prefixes)(bot, msg)`

    Args:
        prefixes (`str`): Prefixes to include alongside mentions.

    Returns:
        A list of the bot's mentions plus whatever prefixes are provided.
    """

    async def new_mention(bot: interactions.Client, _):
        return (await when_mentioned(bot, _)) + list(prefixes)

    return new_mention


async def maybe_coroutine(func: typing.Callable, *args, **kwargs):
    """Allows running either a coroutine or a function."""
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

_pending_regex = r"(1.*2|[^\t\f\v ]+)"
_pending_regex = _pending_regex.replace("1", f"[{''.join(list(_quotes.keys()))}]")
_pending_regex = _pending_regex.replace("2", f"[{''.join(list(_quotes.values()))}]")

ARG_PARSE_REGEX = re.compile(_pending_regex)
MENTION_REGEX = re.compile(r"@(everyone|here|[!&]?[0-9]{17,20})")


def get_args_from_str(input: str) -> list:
    """
    Get arguments from an input string.

    Args:
        input (`str`): The string to process.
    Returns:
        A list of arguments.
    """
    return ARG_PARSE_REGEX.findall(input)


def get_first_word(text: str) -> typing.Optional[str]:
    """
    Get a the first word in a string, regardless of whitespace type.

    Args:
        text (`str`): The text to process.
    Returns:
        The first word, if found.
    """
    return split[0] if (split := text.split(maxsplit=1)) else None


def escape_mentions(content: str) -> str:
    """
    Escape mentions that could ping someone in a string.

    This does not escape channel mentions as they do not ping anybody.

    Args:
        content (`str`): The string to escape.
    Returns:
        The escaped string.
    """
    return MENTION_REGEX.sub("@\u200b\\1", content)
