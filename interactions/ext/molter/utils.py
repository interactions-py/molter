import re
import typing

import interactions

# most of these come from dis-snek
# thanks, polls!


async def when_mentioned(bot: interactions.Client, _):
    return [f"<@{bot.me.id}> ", f"<@!{bot.me.id}> "]  # type: ignore


async def when_mentioned_or(*prefixes: str):
    async def new_mention(bot: interactions.Client, _):
        return await when_mentioned(bot, _) + list(prefixes)

    return new_mention


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
start_quotes = frozenset(_quotes.keys())

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
    return [(arg[1:-1] if arg[0] in start_quotes else arg) for arg in args]


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
