import re
import typing

import interactions
from . import errors
from .context import MolterContext

__all__ = (
    "Converter",
    "LiteralConverter",
    "IDConverter",
    "SnowflakeConverter",
    "MemberConverter",
    "UserConverter",
    "ChannelConverter",
    "Greedy",
    "INTER_OBJECT_TO_CONVERTER",
)


T = typing.TypeVar("T")
T_co = typing.TypeVar("T_co", covariant=True)


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

    def _get_member_from_list(self, members: list[interactions.Member], argument: str):
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
            result = await guild.get_member(int(match.group(1)))
        elif ctx.guild.members:
            result = self._get_member_from_list(ctx.guild.members, argument)
        else:
            query = argument
            if len(argument) > 5 and argument[-5] == "#":
                query, _, _ = argument.rpartition("#")

            members_data = await ctx.client._http.search_guild_members(
                int(ctx.guild.id), query, limit=100
            )
            members = [
                interactions.Member(**data, _client=ctx.client._http)
                for data in members_data
            ]
            result = self._get_member_from_list(members, argument)

        if not result:
            raise errors.BadArgument(f'Member "{argument}" not found.')

        return result


class UserConverter(IDConverter[interactions.User]):
    def _get_tag(self, user: interactions.User):
        return f"{user.username}#{user.discriminator}"

    async def convert(self, ctx: MolterContext, argument: str) -> interactions.User:
        match = self._get_id_match(argument) or re.match(
            r"<@!?([0-9]{15,})>$", argument
        )
        result = None

        if match:
            result = await ctx.client._http.get_user(int(match.group(1)))
            result = interactions.User(**result) if result else None
        else:
            if len(argument) > 5 and argument[-5] == "#":
                result = next(
                    (
                        u
                        for u in ctx.client._http.cache.users.values
                        if self._get_tag(u) == argument
                    ),
                    None,
                )

            if not result:
                result = next(
                    (
                        u
                        for u in ctx.client._http.cache.users.values
                        if u.username == argument
                    ),
                    None,
                )

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
            result = await ctx.client._http.get_channel(int(match.group(1)))
            result = (
                interactions.Channel(**result, _client=ctx.client._http)
                if result
                else None
            )
        elif ctx.guild:

            if ctx.guild.channels:
                channels = [
                    interactions.Channel(**data, _client=ctx.client._http)
                    for data in ctx.guild.channels
                ]
            else:
                channels = await ctx.guild.get_all_channels()

            result = next(
                (c for c in channels if c.name == argument.removeprefix("#")), None
            )

        if not result:
            raise errors.BadArgument(f'Channel "{argument}" not found.')

        return result


class Greedy(typing.List[T]):
    # this class doesn't actually do a whole lot
    # it's more or less simply a note to the parameter
    # getter
    pass


INTER_OBJECT_TO_CONVERTER: dict[type, type[Converter]] = {
    interactions.Snowflake: SnowflakeConverter,
    interactions.Member: MemberConverter,
    interactions.User: UserConverter,
    interactions.Channel: ChannelConverter,
}
