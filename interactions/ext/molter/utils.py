import asyncio
import functools
import inspect
import re
import typing

import interactions
import interactions.api.error as inter_errors

if typing.TYPE_CHECKING:
    from .base import MolterExtension
    from .command import MolterCommand

__all__ = (
    "SnowflakeType",
    "OptionalSnowflakeType",
    "ALL_PERMISSIONS",
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
    "guild_permissions",
    "permissions",
    "Typing",
    "DeferredTyping",
)

# most of these come from naff
# thanks, polls!

SnowflakeType = typing.Union[interactions.Snowflake, int, str]
OptionalSnowflakeType = typing.Optional[SnowflakeType]


T = typing.TypeVar("T")

ALL_PERMISSIONS = interactions.Permissions(0)

for perm in interactions.Permissions:
    ALL_PERMISSIONS |= perm


async def _wrap_lib_exception(function: typing.Awaitable[T]) -> typing.Optional[T]:
    try:
        return await function
    except inter_errors.LibraryException:
        return None


def _wrap_recursive(cmd: "MolterCommand", ext: "MolterExtension"):
    cmd.extension = ext
    cmd.callback = functools.partial(cmd.callback, ext)

    if cmd.error_callback:
        cmd.error_callback = functools.partial(cmd.error_callback, ext)

    for subcommand in cmd.all_commands:
        new_sub = _wrap_recursive(subcommand, ext)

        names = [subcommand.name] + subcommand.aliases
        for name in names:
            cmd.subcommands[name] = new_sub

    return cmd


def remove_prefix(string: str, prefix: str) -> str:
    """
    Removes a prefix from a string if present.

    Args:
        string (`str`): The string to remove the prefix from.
        prefix (`str`): The prefix to remove.

    Returns:
        The string without the prefix.
    """
    return string[len(prefix) :] if string.startswith(prefix) else string[:]


def remove_suffix(string: str, suffix: str) -> str:
    """
    Removes a suffix from a string if present.

    Args:
        string (`str`): The string to remove the suffix from.
        suffix (`str`): The suffix to remove.

    Returns:
        The string without the suffix.
    """
    return string[: -len(suffix)] if string.endswith(suffix) else string[:]


async def when_mentioned(bot: interactions.Client, _) -> typing.List[str]:
    """
    Returns a list of the bot's mentions.

    Returns:
        A list of the bot's possible mentions.
    """
    return [f"<@{bot.me.id}> ", f"<@!{bot.me.id}> "]  # type: ignore


def when_mentioned_or(
    *prefixes: str,
) -> typing.Callable[
    [interactions.Client, typing.Any],
    typing.Coroutine[typing.Any, typing.Any, typing.List[str]],
]:
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


def get_args_from_str(input: str) -> typing.List[str]:
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


def guild_permissions(
    member: interactions.Member, guild: interactions.Guild
) -> interactions.Permissions:
    """
    Computes the guild (role-only) permissions for a member.
    This factors in ownership and the roles of the member.
    This does not take into account implicit permissions.

    This uses the pseudocode featured in Discord's own documentation about
    permission overwrites as a base.

    Returns:
        `interactions.Permissions`: The guild permissions for the member
        that sent the message.
    """

    if int(member.id) == guild.owner_id:
        return ALL_PERMISSIONS

    roles = guild.roles

    role_everyone = next(r for r in roles if r.id == guild.id)
    permissions = interactions.Permissions(int(role_everyone.permissions))

    if member.roles:
        member_roles = [r for r in roles if int(r.id) in member.roles]
    else:
        member_roles = []

    for role in member_roles:
        permissions |= interactions.Permissions(int(role.permissions))

    if (
        permissions & interactions.Permissions.ADMINISTRATOR
        == interactions.Permissions.ADMINISTRATOR
    ):
        return ALL_PERMISSIONS

    return permissions


def _compute_overwrites(
    member: interactions.Member,
    guild: interactions.Guild,
    channel: interactions.Channel,
    base_permissions: interactions.Permissions,
):
    """Calculates and adds in overwrites based on the guild permissions."""

    permissions = base_permissions

    if overwrites := channel.permission_overwrites:
        if overwrite_everyone := next(
            (o for o in overwrites if o.id == str(guild.id)), None
        ):
            permissions &= ~interactions.Permissions(int(overwrite_everyone.deny))
            permissions |= interactions.Permissions(int(overwrite_everyone.allow))

        allow = interactions.Permissions(0)
        deny = interactions.Permissions(0)

        for role_id in member.roles:
            if overwrite_role := next(
                (o for o in overwrites if o.id == str(role_id)), None
            ):
                allow |= interactions.Permissions(int(overwrite_role.allow))
                deny |= interactions.Permissions(int(overwrite_role.deny))

        permissions &= ~deny
        permissions |= allow

        if overwrite_member := next(
            (o for o in overwrites if o.id == str(member.id)), None
        ):
            permissions &= ~interactions.Permissions(int(overwrite_member.deny))
            permissions |= interactions.Permissions(int(overwrite_member.allow))

    return permissions


def permissions(
    member: typing.Union[interactions.Member, interactions.User],
    channel: interactions.Channel,
    guild: typing.Optional[interactions.Guild],
) -> interactions.Permissions:
    """
    Computes the permissions for the member specified.
    This factors in ownership, roles, and channel overwrites.
    This does not take into account implicit permissions.

    This uses the pseudocode featured in Discord's own documentation about
    permission overwrites as a base.

    Returns:
        `interactions.Permissions`: The permissions for the member
        that sent the message.
    """

    if not guild or isinstance(member, interactions.User):
        # basic text permissions, no tts, yes view channel
        return interactions.Permissions(0b1111100110001000000)

    base_permissions = guild_permissions(member, guild)  # type: ignore
    return _compute_overwrites(member, guild, channel, base_permissions)  # type: ignore


class Typing:
    """
    A context manager to send a typing state to a given channel
    as long as long as the wrapped operation takes.

    Args:
        http (`interactions.HTTPClient`): The HTTP client to use.
        channel_id (`int`): The ID of the channel to send the typing state to.
    """

    __slots__ = ("_http", "channel_id", "_stop", "task")

    def __init__(self, http: interactions.HTTPClient, channel_id: int) -> None:
        self._http = http
        self.channel_id = channel_id

        self._stop: bool = False
        self.task = None

    async def _typing_task(self) -> None:
        while not self._stop:
            await self._http.trigger_typing(self.channel_id)
            await asyncio.sleep(5)

    async def __aenter__(self) -> None:
        self.task = asyncio.create_task(self._typing_task())

    async def __aexit__(self, *_) -> None:
        self._stop = True
        self.task.cancel()  # type: ignore


class DeferredTyping:
    """
    A dummy context manager to defer an interaction and then do nothing.

    Args:
        interaction (`interactions.CommandContext`): The interaction to defer.
        ephemeral (`bool`, optional) Whether the response is hidden or not.
    """

    __slots__ = ("interaction", "ephemeral")

    def __init__(
        self, interaction: interactions.CommandContext, ephemeral: bool = False
    ) -> None:
        self.interaction = interaction
        self.ephemeral = ephemeral

    async def __aenter__(self) -> None:
        await self.interaction.defer(self.ephemeral)

    async def __aexit__(self, *_) -> None:
        pass
