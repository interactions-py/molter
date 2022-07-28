import re
import typing

import interactions
import interactions.api.error as inter_errors
from . import errors
from . import utils
from .context import MolterContext
from .utils import _wrap_lib_exception

__all__ = (
    "MolterConverter",
    "NoArgumentConverter",
    "IDConverter",
    "SnowflakeConverter",
    "MemberConverter",
    "UserConverter",
    "ChannelConverter",
    "RoleConverter",
    "GuildConverter",
    "MessageConverter",
    "Greedy",
    "INTER_OBJECT_TO_CONVERTER",
)


T = typing.TypeVar("T")
T_co = typing.TypeVar("T_co", covariant=True)


@typing.runtime_checkable
class MolterConverter(typing.Protocol[T_co]):
    async def convert(self, ctx: MolterContext, argument: str) -> T_co:
        raise NotImplementedError("Derived classes need to implement this.")


class NoArgumentConverter(typing.Generic[T_co]):
    """
    An indicator class for special type of converters that only uses the context.
    Arguments will be "eaten up" by converters otherwise.
    """

    async def convert(self, ctx: MolterContext, argument: str) -> T_co:
        raise NotImplementedError("Derived classes need to implement this.")


class _LiteralConverter(MolterConverter):
    values: typing.Dict

    def __init__(self, args: typing.Any):
        self.values = {arg: type(arg) for arg in args}

    async def convert(self, ctx: MolterContext, argument: str):
        for arg, converter in self.values.items():
            try:
                if (converted := converter(argument)) == arg:
                    return converted
            except Exception:
                continue

        literals_list = [str(a) for a in self.values.keys()]
        literals_str = ", ".join(literals_list[:-1]) + f", or {literals_list[-1]}"
        raise errors.BadArgument(
            f'Could not convert "{argument}" into one of {literals_str}.'
        )


_ID_REGEX = re.compile(r"([0-9]{15,})$")


class IDConverter(MolterConverter[T_co]):
    @staticmethod
    def _get_id_match(argument):
        return _ID_REGEX.match(argument)


class SnowflakeConverter(IDConverter[interactions.Snowflake]):
    async def convert(self, _, argument: str) -> interactions.Snowflake:
        match = self._get_id_match(argument) or re.match(
            r"<(?:@(?:!|&)?|#)([0-9]{15,})>$", argument
        )

        if match is None:
            raise errors.BadArgument(f'"{argument}" is not a valid snowflake.')

        return interactions.Snowflake(match.group(1))


class MemberConverter(IDConverter[interactions.Member]):
    def _get_member_from_list(self, members_data: typing.List[dict], argument: str):
        # sourcery skip: assign-if-exp
        result = None
        if len(argument) > 5 and argument[-5] == "#":
            result = next(
                (
                    m
                    for m in members_data
                    if f"{m['user']['username']}#{m['user']['discriminator']}"
                    == argument
                ),
                None,
            )

        if not result:
            result = next(
                (
                    m
                    for m in members_data
                    if m.get("nick") == argument or m["user"]["username"] == argument
                ),
                None,
            )

        if result is not None:
            return interactions.Member(**result)
        return result

    async def convert(self, ctx: MolterContext, argument: str) -> interactions.Member:
        if not ctx.guild or not ctx.guild_id:
            raise errors.BadArgument("This command cannot be used in private messages.")

        match = self._get_id_match(argument) or re.match(
            r"<@!?([0-9]{15,})>$", argument
        )
        result = None

        if match:
            result = await _wrap_lib_exception(
                interactions.get(
                    ctx.client,
                    interactions.Member,
                    parent_id=int(ctx.guild_id),
                    object_id=int(match.group(1)),
                )
            )
        else:
            query = argument
            if len(argument) > 5 and argument[-5] == "#":
                query, _, _ = argument.rpartition("#")

            members_data = await _wrap_lib_exception(
                ctx._http.search_guild_members(int(ctx.guild_id), query, limit=5)
            )

            if not members_data:
                raise errors.BadArgument(f'Member "{argument}" not found.')

            result = self._get_member_from_list(members_data, argument)

        if not result:
            raise errors.BadArgument(f'Member "{argument}" not found.')

        result._client = ctx._http
        return result


class UserConverter(IDConverter[interactions.User]):
    async def convert(self, ctx: MolterContext, argument: str) -> interactions.User:
        # sourcery skip: remove-redundant-pass
        match = self._get_id_match(argument) or re.match(
            r"<@!?([0-9]{15,})>$", argument
        )
        result = None

        if match:
            result = await _wrap_lib_exception(
                interactions.get(
                    ctx.client, interactions.User, object_id=int(match.group(1))
                )
            )
        else:
            all_cached_users = ctx._http.cache[interactions.User].values.values()
            if len(argument) > 5 and argument[-5] == "#":
                result = next(
                    (
                        u
                        for u in all_cached_users
                        if f"{u.username}#{u.discriminator}" == argument
                    ),
                    None,
                )

            if not result:
                result = next(
                    (u for u in all_cached_users if u.username == argument), None
                )

        if not result:
            raise errors.BadArgument(f'User "{argument}" not found.')

        result._client = ctx._http
        return result


class ChannelConverter(IDConverter[interactions.Channel]):
    async def convert(
        self,
        ctx: MolterContext,
        argument: str,
    ) -> interactions.Channel:
        match = self._get_id_match(argument) or re.match(r"<#([0-9]{15,})>$", argument)
        result = None

        if match:
            result = await _wrap_lib_exception(
                interactions.get(
                    ctx.client, interactions.Channel, object_id=int(match.group(1))
                )
            )
        elif ctx.guild and ctx.guild.channels:
            result = next(
                (
                    c
                    for c in ctx.guild.channels
                    if c.name == utils.remove_prefix(argument, "#")
                ),
                None,
            )

        if not result:
            raise errors.BadArgument(f'Channel "{argument}" not found.')

        result._client = ctx._http
        return result


class RoleConverter(IDConverter[interactions.Role]):
    async def convert(
        self,
        ctx: MolterContext,
        argument: str,
    ) -> interactions.Role:
        if not ctx.guild_id or not ctx.guild:
            raise errors.BadArgument("This command cannot be used in private messages.")

        # while i'd like to use the cache here, roles don't store info about which guild they come
        # from, and the guild doesn't update its role list
        match = self._get_id_match(argument) or re.match(r"<@&([0-9]{15,})>$", argument)
        result = None

        if match:
            result = await _wrap_lib_exception(
                interactions.get(
                    ctx.client,
                    interactions.Role,
                    parent_id=int(ctx.guild_id),
                    object_id=int(match.group(1)),
                )
            )
        else:
            result = next(
                (r for r in ctx.guild.roles if r.name == argument),
                None,
            )

        if not result:
            raise errors.BadArgument(f'Role "{argument}" not found.')

        return interactions.Role(**result, _client=ctx._http)  # type: ignore


class GuildConverter(IDConverter[interactions.Guild]):
    async def convert(self, ctx: MolterContext, argument: str) -> interactions.Guild:
        if match := self._get_id_match(argument):
            result = await _wrap_lib_exception(
                interactions.get(
                    ctx.client, interactions.Guild, object_id=int(match.group(1))
                )
            )
        else:
            result = next((g for g in ctx.bot.guilds if g.name == argument), None)

        if not result:
            raise errors.BadArgument(f'Guild "{argument}" not found.')

        result._client = ctx._http
        return result


class MessageConverter(MolterConverter[interactions.Message]):
    # either just the id or <chan_id>-<mes_id>, a format you can get by shift clicking "copy id"
    _ID_REGEX = re.compile(
        r"(?:(?P<channel_id>[0-9]{15,})-)?(?P<message_id>[0-9]{15,})"
    )
    # of course, having a way to get it from a link is nice
    _MESSAGE_LINK_REGEX = re.compile(
        r"https?://[\S]*?discord(?:app)?\.com/channels/(?P<guild_id>[0-9]{15,}|@me)/"
        r"(?P<channel_id>[0-9]{15,})/(?P<message_id>[0-9]{15,})\/?$"
    )

    async def convert(self, ctx: MolterContext, argument: str) -> interactions.Message:
        match = self._ID_REGEX.match(argument) or self._MESSAGE_LINK_REGEX.match(
            argument
        )
        if not match:
            raise errors.BadArgument(f'Message "{argument}" not found.')

        data = match.groupdict()

        message_id = int(data["message_id"])
        channel_id = (
            int(data["channel_id"]) if data.get("channel_id") else int(ctx.channel_id)
        )

        # this guild checking is technically unnecessary, but we do it just in case
        # it means a user cant just provide an invalid guild id and still get a message
        guild_id = data["guild_id"] if data.get("guild_id") else ctx.guild_id
        guild_id = str(guild_id) if guild_id != "@me" else None

        if cached_message := ctx._http.cache[interactions.Message].get(
            interactions.Snowflake(message_id)
        ):
            if int(cached_message.channel_id) == channel_id and (
                cached_message.guild_id == guild_id
                or str(cached_message.guild_id == guild_id)
            ):
                return cached_message
            else:
                raise errors.BadArgument(f'Message "{argument}" not found.')

        try:
            message_data: dict = await ctx._http.get_message(channel_id, message_id)  # type: ignore

            msg_guild_id: typing.Optional[str] = message_data.get("guild_id")
            if not msg_guild_id:
                if channel := ctx._http.cache[interactions.Channel].get(
                    interactions.Snowflake(channel_id)
                ):
                    msg_guild_id = message_data["guild_id"] = (
                        str(channel.guild_id) if channel.guild_id else None
                    )
                else:
                    channel_data = await _wrap_lib_exception(
                        ctx._http.get_channel(channel_id)
                    )
                    if channel_data:
                        msg_guild_id = message_data["guild_id"] = channel_data.get(
                            "guild_id"
                        )
                    else:
                        raise errors.BadArgument(f'Message "{argument}" not found.')

            if msg_guild_id != guild_id:
                raise errors.BadArgument(f'Message "{argument}" not found.')

            return interactions.Message(**message_data, _client=ctx._http)  # type: ignore
        except inter_errors.LibraryException:
            raise errors.BadArgument(f'Message "{argument}" not found.')


class AttachmentConverter(NoArgumentConverter[interactions.Attachment]):
    async def convert(self, ctx: MolterContext, _) -> interactions.Attachment:
        # could be edited by a dev, but... why
        attachment_counter: int = ctx.extras.get("__molter_attachment_counter", 0)

        try:
            attach = ctx.message.attachments[attachment_counter]
            ctx.extras["__molter_attachment_counter"] = attachment_counter + 1
            return attach
        except IndexError:
            raise errors.BadArgument("There are no more attachments for this context.")


class Greedy(typing.List[T]):
    # this class doesn't actually do a whole lot
    # it's more or less simply a note to the parameter
    # getter
    pass


INTER_OBJECT_TO_CONVERTER: typing.Dict[type, typing.Type[MolterConverter]] = {
    interactions.Snowflake: SnowflakeConverter,
    interactions.Member: MemberConverter,
    interactions.User: UserConverter,
    interactions.Channel: ChannelConverter,
    interactions.Role: RoleConverter,
    interactions.Guild: GuildConverter,
    interactions.Message: MessageConverter,
    interactions.Attachment: AttachmentConverter,  # type: ignore
}
