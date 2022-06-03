import inspect
import typing
from copy import deepcopy
from functools import wraps

import interactions
from . import converters
from . import errors
from .command import MolterCommand
from .context import HybridContext
from interactions.client.decor import command as slash_command

__all__ = ("extension_hybrid_slash",)


def _match_option_type(option_type: int):
    if option_type in {1, 2}:
        raise ValueError("Hybrid commands do not support subcommand options right now.")
    if option_type == 3:
        return str
    if option_type == 4:
        return int
    if option_type == 5:
        return bool
    if option_type == 6:
        return typing.Union[interactions.Member, interactions.User]
    if option_type == 7:
        return interactions.Channel
    if option_type == 8:
        return interactions.Role
    if option_type == 9:
        return typing.Union[interactions.Member, interactions.User, interactions.Role]
    if option_type == 10:
        return float
    if option_type == 11:
        return interactions.Attachment

    raise ValueError(f"{option_type} is an unsupported option type right now.")


def _generate_permission_check(_permissions: int):
    permissions = interactions.Permissions(_permissions)

    async def _permission_check(ctx: HybridContext):
        member_permissions = await ctx.compute_permissions()
        result = permissions in member_permissions

        if not result:
            raise errors.CheckFailure(
                ctx, "You do not have the proper permissions to use this command."
            )
        return result

    return _permission_check


def _generate_scope_check(_scopes: typing.List[int]):
    async def _scope_check(ctx: HybridContext):
        if ctx.guild_id not in _scopes:
            raise errors.CheckFailure(
                ctx, "You cannot use this command in this server."
            )
        return True

    return _scope_check


async def _guild_check(ctx: HybridContext):
    if not ctx.guild_id:
        raise errors.CheckFailure(
            ctx, "This command cannot be used in private messages."
        )
    return True


class _RangeConverter(converters.MolterConverter[typing.Union[float, int]]):
    def __init__(
        self,
        number_type: typing.Type,
        min_value: typing.Optional[typing.Union[float, int]],
        max_value: typing.Optional[typing.Union[float, int]],
    ):
        self.number_type = number_type
        self.min_value = min_value
        self.max_value = max_value

    async def convert(
        self, ctx: HybridContext, argument: str
    ) -> typing.Union[float, int]:
        try:
            converted: typing.Union[float, int] = self.number_type(argument)

            if self.min_value and converted < self.min_value:
                raise errors.BadArgument(
                    f'Value "{argument}" is less than {self.min_value}.'
                )
            if self.max_value and converted > self.max_value:
                raise errors.BadArgument(
                    f'Value "{argument}" is greater than {self.max_value}.'
                )

            return converted
        except ValueError:
            type_name: str = self.number_type.__name__

            if type_name.startswith("i"):
                raise errors.BadArgument(
                    f'Argument "{argument}" is not an {type_name}.'
                )
            else:
                raise errors.BadArgument(f'Argument "{argument}" is not a {type_name}.')
        except errors.BadArgument:
            raise


class _NarrowedChannelConverter(converters.ChannelConverter):
    def __init__(self, channel_types: typing.List[interactions.ChannelType]):
        self.channel_types = channel_types

    async def convert(self, ctx: HybridContext, argument: str):
        channel = await super().convert(ctx, argument)
        if channel.type not in self.channel_types:
            raise errors.BadArgument(
                f'Channel "{argument}" is not a valid channel type.'
            )
        return channel


def _molter_from_slash(coro_copy: typing.Callable, **kwargs):
    # welcome to hell.

    if cmd_type := kwargs.get("type"):
        if cmd_type not in {1, interactions.ApplicationCommandType.CHAT_INPUT}:
            raise ValueError("Hybrid commands only support slash commands.")

    if (options := kwargs.get("options")) and options is not interactions.MISSING:
        options: typing.Union[
            typing.Dict[str, typing.Any],
            typing.List[typing.Dict[str, typing.Any]],
            interactions.Option,
            typing.List[interactions.Option],
        ]

        if all(isinstance(option, interactions.Option) for option in options):
            _options = [option._json for option in options]
        elif all(
            isinstance(option, dict) and all(isinstance(value, str) for value in option)
            for option in options
        ):
            _options = list(options)
        elif isinstance(options, interactions.Option):
            _options = [options._json]
        else:
            _options = [options]

        _options: typing.List[typing.Dict]

        for _option in _options:
            option = interactions.Option(**_option)

            annotation = _match_option_type(option.type.value)

            if annotation in {str, int, float} and option.choices:
                if any(c.name != c.value for c in option.choices):
                    raise ValueError(
                        "Hybrid commands do not support choices that have a"
                        " different value compared to its name."
                    )

                annotation = converters._LiteralConverter(
                    tuple(c.name for c in option.choices)
                )
            elif annotation in {int, float} and (
                option.min_value is not None or option.max_value is not None
            ):
                annotation = _RangeConverter(
                    annotation, option.min_value, option.max_value
                )
            elif annotation == interactions.Channel and option.channel_types:
                annotation = _NarrowedChannelConverter(option.channel_types)

            if not option.required:
                annotation = typing.Optional[annotation]  # type: ignore

            coro_copy.__annotations__[option.name] = annotation

    name: str = (
        kwargs.get("name")
        if (name := kwargs.get("name")) and name is not interactions.MISSING
        else coro_copy.__name__  # type: ignore
    )

    description = (
        kwargs.get("description")
        if (description := kwargs.get("description"))
        and description is not interactions.MISSING
        else None
    )

    molt_cmd = MolterCommand(  # type: ignore
        callback=coro_copy,
        name=name,
        help=description,
        brief=None,
    )

    if (scope := kwargs.get("scope")) and scope is not interactions.MISSING:  # type: ignore
        scope: typing.Union[
            int,
            interactions.Guild,
            typing.List[int],
            typing.List[interactions.Guild],
        ]

        _scopes = []

        if isinstance(scope, list):
            if all(isinstance(guild, interactions.Guild) for guild in scope):
                [_scopes.append(int(guild.id)) for guild in scope]
            elif all(isinstance(guild, int) for guild in scope):
                [_scopes.append(guild) for guild in scope]
        elif isinstance(scope, interactions.Guild):
            _scopes.append(int(scope.id))
        else:
            _scopes.append(scope)

        molt_cmd.checks.append(_generate_scope_check(_scopes))  # type: ignore

    if (
        default_member_permissions := kwargs.get("default_member_permissions")  # type: ignore
    ) and default_member_permissions is not interactions.MISSING:
        default_member_permissions: typing.Union[int, interactions.Permissions]

        if isinstance(default_member_permissions, interactions.Permissions):
            default_member_permissions = default_member_permissions.value

        molt_cmd.checks.append(
            _generate_permission_check(default_member_permissions)  # type: ignore
        )

    if kwargs.get("dm_permissions") is False:
        molt_cmd.checks.append(_guild_check)  # type: ignore

    return molt_cmd


@wraps(slash_command)
def extension_hybrid_slash(*args, **kwargs):
    """
    A decorator for creating hybrid commands based off a normal slash command.
    Uses all normal slash command arguments (besides for type), but also makes
    a prefixed command when used in conjunction with `MolterExtension`.

    Remember to use `HybridContext` as the context for proper type hinting.
    """

    def decorator(coro):
        # we're about to do some evil things, let's not destroy everything
        coro_copy = deepcopy(coro)
        molt_cmd = _molter_from_slash(coro_copy, **kwargs)

        async def wrapped_command(
            self, ctx: interactions.CommandContext, *args, **kwargs
        ):
            new_ctx = HybridContext(
                message=ctx.message,
                user=ctx.user,
                member=ctx.member,
                channel=ctx.channel,
                guild=ctx.guild,
                prefix="/",
                interaction=ctx,
            )
            await coro(self, new_ctx, *args, **kwargs)

        wrapped_command.__molter_command__ = molt_cmd
        return interactions.extension_command(*args, **kwargs)(wrapped_command)

    return decorator
