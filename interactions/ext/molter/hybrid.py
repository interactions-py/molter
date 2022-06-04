import inspect
import typing
from copy import deepcopy
from functools import wraps

import interactions
from . import command
from . import converters
from . import errors
from .context import HybridContext
from .utils import _qualname_self_check
from .utils import _qualname_wrap
from interactions.client.decor import command as slash_command

__all__ = ("extension_hybrid_slash",)

# welcome to hell.
# saying this code is messy is an understatement


def _variable_to_options(
    options: typing.Union[
        typing.Dict[str, typing.Any],
        typing.List[typing.Dict[str, typing.Any]],
        interactions.Option,
        typing.List[interactions.Option],
    ]
):
    # even if its typehinted as Option, inter.py doesn't guarantee it is
    if all(isinstance(option, interactions.Option) for option in options):  # type: ignore
        _options = [option._json for option in options]  # type: ignore
    elif all(
        isinstance(option, dict) and all(isinstance(value, str) for value in option)
        for option in options  # type: ignore
    ):
        _options = list(options)  # type: ignore
    elif isinstance(options, interactions.Option):
        _options = [options._json]
    else:
        _options = [options]  # type: ignore

    _options: typing.List[typing.Dict]
    return [interactions.Option(**option) for option in _options]


def _variable_to_choices(choices):
    # ditto, but with choices
    if all(isinstance(choice, dict) for choice in choices):
        _choices = [
            choice if isinstance(choice, dict) else choice._json for choice in choices
        ]
    elif all(isinstance(choice, interactions.Choice) for choice in choices):
        _choices = [choice._json for choice in choices]
    else:
        _choices = choices

    return [interactions.Choice(**choice) for choice in _choices]


def _match_option_type(option_type: int):
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


def _basic_subcommand_generator(name: str, description: str, group: bool = False):
    async def _subcommand_base(*args, **kwargs):
        if group:
            raise errors.BadArgument(
                "Cannot run this base command without a subcommand."
            )
        else:
            raise errors.BadArgument(
                "Cannot run this subcommand group without a subcommand."
            )

    subcommand_base = command.MolterCommand(
        callback=_subcommand_base,
        name=name,
        signature=inspect.Signature(None),  # type: ignore
    )

    return subcommand_base


def _options_to_parameters(
    options: typing.List[interactions.Option],
    ori_parameters: typing.Dict[str, inspect.Parameter],
):
    new_parameters: typing.List[inspect.Parameter] = []

    for option in options:
        annotation = _match_option_type(option.type.value)

        if annotation in {str, int, float} and option.choices:
            actual_choices = _variable_to_choices(option.choices)

            if any(c.name != c.value for c in actual_choices):
                raise ValueError(
                    "Hybrid commands do not support choices that have a"
                    " different value compared to its name."
                )

            annotation = converters._LiteralConverter(
                tuple(c.name for c in actual_choices)
            )
        elif annotation in {int, float} and (
            option.min_value is not None or option.max_value is not None
        ):
            annotation = _RangeConverter(annotation, option.min_value, option.max_value)
        elif annotation == interactions.Channel and option.channel_types:
            annotation = _NarrowedChannelConverter(option.channel_types)

        if ori_param := ori_parameters.get(option.name):
            kind = (
                ori_param.kind
                if ori_param.kind
                not in {inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.VAR_KEYWORD}
                else inspect.Parameter.POSITIONAL_OR_KEYWORD
            )
            kind = (
                ori_param.kind
                if ori_param.kind != inspect.Parameter.VAR_POSITIONAL
                else inspect.Parameter.POSITIONAL_ONLY
            )
            default = ori_param.default
        else:
            kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
            default = inspect._empty

        new_parameters.append(
            inspect.Parameter(
                option.name,
                kind,
                default=default,
                annotation=annotation,
            )
        )

    return new_parameters


def generate_subcommand_func(
    coro_copy: typing.Callable, name: str, group_name: typing.Optional[str] = None
):
    if _qualname_self_check(coro_copy):

        async def _subcommand_func(self, ctx: HybridContext, *args, **kwargs):  # type: ignore
            if group_name:
                return await coro_copy(self, ctx, group_name, name, *args, **kwargs)
            else:
                return await coro_copy(self, ctx, name, *args, **kwargs)

    else:

        async def _subcommand_func(ctx: HybridContext, *args, **kwargs):
            if group_name:
                return await coro_copy(ctx, group_name, name, *args, **kwargs)
            else:
                return await coro_copy(ctx, name, *args, **kwargs)

    return _subcommand_func


def _subcommand_to_molter(
    base_name: str,
    description: str,
    options: typing.List[interactions.Option],
    coro_copy: typing.Callable,
    ori_parameters: typing.Dict[str, inspect.Parameter],
    group_name: typing.Optional[str] = None,
):
    base_command = _basic_subcommand_generator(base_name, description)

    for subcommand_option in options:

        new_parameters = None
        if subcommand_option.options:
            params = _options_to_parameters(
                _variable_to_options(subcommand_option.options), ori_parameters
            )
            new_parameters = inspect.Signature(params)

        _sub_func = generate_subcommand_func(
            coro_copy, subcommand_option.name, group_name
        )

        subcommand = command.MolterCommand(
            callback=_sub_func,
            name=subcommand_option.name,
            help=subcommand_option.description,
            signature=new_parameters,  # type: ignore
        )
        base_command.add_command(subcommand)

    return base_command


def _subcommand_group_to_molter(
    base_name: str,
    description: str,
    options: typing.List[interactions.Option],
    coro_copy: typing.Callable,
    ori_parameters: typing.Dict[str, inspect.Parameter],
):
    base_command = _basic_subcommand_generator(base_name, description, group=True)

    for subcommand_group_option in options:
        subcommand = _subcommand_to_molter(
            subcommand_group_option.name,
            subcommand_group_option.description,
            _variable_to_options(subcommand_group_option.options),  # type: ignore
            coro_copy,
            ori_parameters,
            base_name,
        )
        base_command.add_command(subcommand)

    return base_command


def _molter_from_slash(coro_copy: typing.Callable, **kwargs):
    name: str = (
        kwargs.get("name")
        if (name := kwargs.get("name")) and name is not interactions.MISSING  # type: ignore
        else coro_copy.__name__  # type: ignore
    )

    description: str = (
        kwargs.get("description")
        if (description := kwargs.get("description"))  # type: ignore
        and description is not interactions.MISSING  # type: ignore
        else None
    )  # type: ignore

    molt_cmd: typing.Optional[command.MolterCommand] = None

    if (options := kwargs.get("options")) and options is not interactions.MISSING:  # type: ignore
        options = _variable_to_options(options)

        signature = inspect.signature(_qualname_wrap(coro_copy))
        ori_parameters: typing.Dict[str, inspect.Parameter] = signature.parameters  # type: ignore

        first_option = options[0]

        if first_option.type.value in {1, 2} and first_option.options:
            if first_option.type == interactions.OptionType.SUB_COMMAND:
                molt_cmd = _subcommand_to_molter(
                    name, description, options, coro_copy, ori_parameters
                )

            elif first_option.type == interactions.OptionType.SUB_COMMAND_GROUP:
                molt_cmd = _subcommand_group_to_molter(
                    name, description, options, coro_copy, ori_parameters
                )

        if not molt_cmd:
            new_parameters = _options_to_parameters(options, ori_parameters)
            new_signature = inspect.Signature(new_parameters)

            molt_cmd = command.MolterCommand(
                callback=coro_copy,
                name=name,
                help=description,
                signature=new_signature,  # type: ignore
            )
    else:
        molt_cmd = command.MolterCommand(
            callback=coro_copy,
            name=name,
            help=description,
            signature=inspect.Signature(None),  # type: ignore
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
                [_scopes.append(int(guild.id)) for guild in scope]  # type: ignore
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
def extension_hybrid_slash(
    *,
    name: typing.Optional[str] = interactions.MISSING,  # type: ignore
    description: typing.Optional[str] = interactions.MISSING,  # type: ignore
    scope: typing.Optional[
        typing.Union[
            int,
            interactions.Guild,
            typing.List[int],
            typing.List[interactions.Guild],
        ]
    ] = interactions.MISSING,  # type: ignore
    options: typing.Optional[
        typing.Union[
            typing.Dict[str, typing.Any],
            typing.List[typing.Dict[str, typing.Any]],
            interactions.Option,
            typing.List[interactions.Option],
        ]
    ] = interactions.MISSING,  # type: ignore
    name_localizations: typing.Optional[
        typing.Dict[typing.Union[str, interactions.Locale], str]
    ] = interactions.MISSING,  # type: ignore
    description_localizations: typing.Optional[
        typing.Dict[typing.Union[str, interactions.Locale], str]
    ] = interactions.MISSING,  # type: ignore
    default_member_permissions: typing.Optional[
        typing.Union[int, interactions.Permissions]
    ] = interactions.MISSING,  # type: ignore
    dm_permission: typing.Optional[bool] = interactions.MISSING,  # type: ignore
):
    """
    A decorator for creating hybrid commands based off a normal slash command.
    Uses all normal slash command arguments (besides for type), but also makes
    a prefixed command when used in conjunction with `MolterExtension`.

    Remember to use `HybridContext` as the context for proper type hinting.
    Subcommand options do not work with this decorator right now.
    """

    kwargs = locals()
    kwargs["type"] = interactions.ApplicationCommandType.CHAT_INPUT

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
            new_ctx.args = list(args) + list(kwargs.values())
            await coro(self, new_ctx, *args, **kwargs)

        wrapped_command.__molter_command__ = molt_cmd
        return interactions.extension_command(**kwargs)(wrapped_command)

    return decorator
