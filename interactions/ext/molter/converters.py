import re
import typing

import interactions
import interactions.api.error as inter_errors
from . import errors
from . import utils
from .context import MolterContext

__all__ = (
    "Converter",
    "LiteralConverter",
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


async def _wrap_http_exception(
    function: typing.Coroutine[typing.Any, typing.Any, T]
) -> typing.Optional[T]:
    try:
        return await function
    except inter_errors.HTTPException:
        return None


@typing.runtime_checkable
class Converter(typing.Protocol[T_co]):
    async def convert(self, ctx: MolterContext, argument: str) -> T_co:
        raise NotImplementedError("Derived classes need to implement this.")


class LiteralConverter(Converter):
    values: typing.Dict

    def __init__(self, args: typing.Any):
        self.values = {arg: type(arg) for arg in args}

    async def convert(self, ctx: MolterContext, argument: str):
        for arg, converter in self.values.items():
            try:
                if arg == converter(argument):
                    return argument
            except Exception:
                continue

        literals_list = [str(a) for a in self.values.keys()]
        literals_str = ", ".join(literals_list[:-1]) + f", or {literals_list[-1]}"
        raise errors.BadArgument(
            f'Could not convert "{argument}" into one of {literals_str}.'
        )


_ID_REGEX = re.compile(r"([0-9]{15,})$")


class IDConverter(Converter[T_co]):
    @staticmethod
    def _get_id_match(argument):
        return _ID_REGEX.match(argument)


class SnowflakeConverter(IDConverter[interactions.Snowflake]):
    async def convert(self, _, argument: str) -> interactions.Snowflake:
        match = self._get_id_match(argument) or re.match(
            r"<(?:@(?:!|&)?|#)([0-9]{15,})>$", argument
        )

        if match is None:
            raise errors.BadArgument(argument)

        return interactions.Snowflake(match.group(1))


class MemberConverter(IDConverter[interactions.Member]):
    def _display_name(self, member: interactions.Member):
        return member.nick or member.user.username

    def _get_member_from_list(
        self, members: typing.List[interactions.Member], argument: str
    ):
        result = None
        if len(argument) > 5 and argument[-5] == "#":
            result = next(
                (
                    m
                    for m in members
                    if f"{m.user.username}#{m.user.discriminator}" == argument
                ),
                None,
            )

        if not result:
            result = next(
                (
                    m
                    for m in members
                    if self._display_name(m) == argument or m.user.username == argument
                ),
                None,
            )

        return result

    async def convert(self, ctx: MolterContext, argument: str) -> interactions.Member:
        if not ctx.guild_id:
            raise errors.BadArgument("This command cannot be used in private messages.")

        guild = await ctx.get_guild()
        match = self._get_id_match(argument) or re.match(
            r"<@!?([0-9]{15,})>$", argument
        )
        result = None

        if match:
            result = await _wrap_http_exception(guild.get_member(int(match.group(1))))
        else:
            query = argument
            if len(argument) > 5 and argument[-5] == "#":
                query, _, _ = argument.rpartition("#")

            members_data = await _wrap_http_exception(
                ctx.client._http.search_guild_members(
                    int(ctx.guild_id), query, limit=100
                )
            )
            if not members_data:
                raise errors.BadArgument(f'Member "{argument}" not found.')

            members = [
                interactions.Member(**data, _client=ctx.client._http)
                for data in members_data
            ]
            result = self._get_member_from_list(members, argument)

        if not result:
            raise errors.BadArgument(f'Member "{argument}" not found.')

        return result


class UserConverter(IDConverter[interactions.User]):
    async def convert(self, ctx: MolterContext, argument: str) -> interactions.User:
        # sourcery skip: remove-redundant-pass
        match = self._get_id_match(argument) or re.match(
            r"<@!?([0-9]{15,})>$", argument
        )
        result = None

        if match:
            result = await _wrap_http_exception(
                ctx.client._http.get_user(int(match.group(1)))
            )
            if result:
                result = interactions.User(**result)
        else:
            # sadly, ids are the only viable way of getting
            # accurate user objects in a reasonable manner
            # if we did names, we would have to use the cache, which
            # doesnt update on username changes or anything,
            # and so may have the wrong name
            # erroring out is better than wrong data to me
            # though its easy enough subclassing this to change that
            pass

        if not result:
            raise errors.BadArgument(f'User "{argument}" not found.')

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
            result = await _wrap_http_exception(
                ctx.client._http.get_channel(int(match.group(1)))
            )
            if result:
                result = interactions.Channel(**result, _client=ctx.client._http)
        elif ctx.guild_id:
            guild = await ctx.get_guild()
            channels = await guild.get_all_channels()
            result = next(
                (c for c in channels if c.name == utils.remove_prefix(argument, "#")),
                None,
            )

        if not result:
            raise errors.BadArgument(f'Channel "{argument}" not found.')

        return result


class RoleConverter(IDConverter[interactions.Role]):
    async def convert(
        self,
        ctx: MolterContext,
        argument: str,
    ) -> interactions.Role:
        if not ctx.guild_id:
            raise errors.BadArgument("This command cannot be used in private messages.")

        guild = await ctx.get_guild()
        match = self._get_id_match(argument) or re.match(r"<@&([0-9]{15,})>$", argument)
        result = None

        if match:
            # this is faster than using get_role and is also accurate
            result = next((r for r in guild.roles if str(r.id) == match.group(1)), None)
        else:
            result = next(
                (r for r in guild.roles if r.name == argument),
                None,
            )

        if not result:
            raise errors.BadArgument(f'Role "{argument}" not found.')

        return result


class GuildConverter(IDConverter[interactions.Guild]):
    async def convert(self, ctx: MolterContext, argument: str) -> interactions.Guild:
        match = self._get_id_match(argument)
        guild_id: typing.Optional[int] = None

        if match:
            guild_id = int(match.group(1))
        else:
            # we can only use guild ids for the same reason we can only use user ids
            # for the user converter
            # there is an http endpoint to get all guilds a bot is in
            # but if the bot has a ton of guilds, this would be too intensive
            raise errors.BadArgument(f'Guild "{argument}" not found.')

        try:
            guild_data = await ctx.client._http.get_guild(guild_id)
            return interactions.Guild(**guild_data, _client=ctx.client._http)
        except inter_errors.HTTPException:
            raise errors.BadArgument(f'Guild "{argument}" not found.')


class MessageConverter(Converter[interactions.Message]):
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
            int(ctx.channel_id)
            if not data.get("channel_id")
            else int(data["channel_id"])
        )

        # this guild checking is technically unnecessary, but we do it just in case
        # it means a user cant just provide an invalid guild id and still get a message
        guild_id = ctx.guild_id if not data.get("guild_id") else data["guild_id"]
        guild_id = int(guild_id) if guild_id != "@me" else None

        try:
            message_data = await ctx.client._http.get_message(channel_id, message_id)
            if message_data.get("guild_id") != guild_id:
                raise errors.BadArgument(f'Message "{argument}" not found.')
            return interactions.Message(**message_data, _client=ctx.client._http)
        except inter_errors.HTTPException:
            raise errors.BadArgument(f'Message "{argument}" not found.')


class Greedy(typing.List[T]):
    # this class doesn't actually do a whole lot
    # it's more or less simply a note to the parameter
    # getter
    pass


INTER_OBJECT_TO_CONVERTER: typing.Dict[type, typing.Type[Converter]] = {
    interactions.Snowflake: SnowflakeConverter,
    interactions.Member: MemberConverter,
    interactions.User: UserConverter,
    interactions.Channel: ChannelConverter,
    interactions.Role: RoleConverter,
    interactions.Guild: GuildConverter,
    interactions.Message: MessageConverter,
}
