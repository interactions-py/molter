import collections
import contextlib
import functools
import inspect
import typing

import attrs
import typing_extensions

import interactions
from . import context
from . import converters
from . import errors
from .utils import _start_quotes
from .utils import maybe_coroutine

__all__ = (
    "MolterCommand",
    "prefixed_command",
    "prefix_command",
    "text_command",
    "text_based_command",
    "register_converter",
    "globally_register_converter",
    "prefixed_parameter",
    "ext_error_handler",
)


if typing.TYPE_CHECKING:
    from .base import MolterExtension

# 3.8+ compatibility
NoneType = type(None)

try:
    from types import UnionType  # type: ignore

    UNION_TYPES = {typing.Union, UnionType}
except ImportError:  # 3.8-3.9
    UNION_TYPES = {typing.Union}


# thankfully, modules are singletons
_global_type_to_converter = dict(converters.INTER_OBJECT_TO_CONVERTER)

ERROR_HANDLER = typing.Callable[
    [context.MolterContext, Exception], typing.Awaitable[typing.Any]
]
EXT_ERROR_HANDLER = typing.Callable[
    [typing.Any, context.MolterContext, Exception], typing.Awaitable[typing.Any]
]
# for some reason, typing an ext here doesn't work, so oh well
ERROR_HANDLER_FUNCTION = typing.Union[ERROR_HANDLER, EXT_ERROR_HANDLER]

EEH = typing.TypeVar("EEH", bound=EXT_ERROR_HANDLER)
EHF = typing.TypeVar("EHF", bound=ERROR_HANDLER_FUNCTION)


class ParameterInfo(typing.TypedDict):
    default: typing.Union[
        typing.Callable[[context.MolterContext, str], typing.Any], typing.Any
    ]


@attrs.define(slots=True)
class PrefixedCommandParameter:
    """
    An object representing parameters in a prefixed command.
    This class should not be instantiated directly.
    """

    name: str = attrs.field(default=None)
    "The name of the parameter."
    default: typing.Any = attrs.field(default=interactions.MISSING)
    "The default value of the parameter."
    type: typing.Type = attrs.field(default=None)
    "The type of the parameter."
    kind: inspect._ParameterKind = attrs.field(
        default=inspect.Parameter.POSITIONAL_OR_KEYWORD
    )
    """The kind of parameter this is as related to the function."""
    converters: typing.List[
        typing.Callable[[context.MolterContext, str], typing.Any]
    ] = attrs.field(factory=list)
    "A list of the converter functions for the parameter that convert to its type."
    greedy: bool = attrs.field(default=False)
    "Is the parameter greedy?"
    union: bool = attrs.field(default=False)
    "Is the parameter a union?"
    variable: bool = attrs.field(default=False)
    "Was the parameter marked as a variable argument?"
    consume_rest: bool = attrs.field(default=False)
    "Was the parameter marked to consume the rest of the input?"
    no_argument: bool = attrs.field(default=False)
    "Does this parameter have a converter that subclasses `NoArgumentConverter`?"

    @property
    def optional(self) -> bool:
        """Is this parameter optional?"""
        return self.default != interactions.MISSING


@attrs.define(slots=True)
class _PrefixedArgsIterator:
    """
    An iterator over the arguments of a prefixed command.
    Has functions to control the iteration.
    """

    args: typing.Tuple[str] = attrs.field()
    index: int = attrs.field(init=False, default=0)
    length: int = attrs.field(init=False, default=0)

    def __iter__(self) -> typing_extensions.Self:
        self.length = len(self.args)
        return self

    def __next__(self) -> str:
        if self.index >= self.length:
            raise StopIteration

        result = self.args[self.index]
        self.index += 1
        return self._remove_quotes(result)

    def _remove_quotes(self, arg: str) -> str:
        # this removes quotes from the arguments themselves
        return arg[1:-1] if arg[0] in _start_quotes else arg

    def _finish_args(self) -> typing.Tuple[str]:
        result = self.args[self.index - 1 :]
        self.index = self.length
        return result

    def get_rest_of_args(self) -> typing.Tuple[str]:
        return tuple(self._remove_quotes(r) for r in self._finish_args())

    def consume_rest(self) -> str:
        return " ".join(self._finish_args())

    def back(self, count: int = 1) -> None:
        self.index -= count

    def reset(self) -> None:
        self.index = 0

    @property
    def finished(self) -> bool:
        return self.index >= self.length


def _get_name(x: typing.Any):
    try:
        return x.__name__
    except AttributeError:
        return repr(x) if hasattr(x, "__origin__") else x.__class__.__name__


def _convert_to_bool(argument: str) -> bool:
    lowered = argument.lower()
    if lowered in {"yes", "y", "true", "t", "1", "enable", "on"}:
        return True
    elif lowered in {"no", "n", "false", "f", "0", "disable", "off"}:
        return False
    else:
        raise errors.BadArgument(f"{argument} is not a recognised boolean option.")


def _merge_converters(
    converter_dict: typing.Dict[type, typing.Type[converters.MolterConverter]]
) -> typing.Dict[type, typing.Type[converters.MolterConverter]]:
    # sourcery skip: dict-assign-update-to-union
    global _global_type_to_converter
    combined = dict(_global_type_to_converter)
    combined.update(converter_dict)
    return combined


def _get_from_anno_type(anno: typing_extensions.Annotated):
    """
    Handles dealing with Annotated annotations, getting their (first) type annotation.
    This allows correct type hinting with, say, Converters,
    for example.
    """
    # this is treated how it usually is during runtime
    # the first argument is ignored and the rest is treated as is
    args = typing_extensions.get_args(anno)[1:]
    return args[0]


def _get_converter_function(
    anno: typing.Union[
        typing.Type[converters.MolterConverter], converters.MolterConverter
    ],
    name: str,
) -> typing.Callable[[context.MolterContext, str], typing.Any]:
    num_params = len(inspect.signature(anno.convert).parameters.values())

    # if we have three parameters for the function, it's likely it has a self parameter
    # so we need to get rid of it by initing - typehinting hates this, btw!
    # the below line will error out if we aren't supposed to init it, so that works out
    actual_anno: converters.MolterConverter = anno() if num_params == 3 else anno  # type: ignore
    # we can only get to this point while having three params if we successfully inited
    if num_params == 3:
        num_params -= 1

    if num_params != 2:
        ValueError(
            f"{_get_name(anno)} for {name} is invalid: converters must have exactly 2"
            " arguments."
        )

    return actual_anno.convert


def _get_converter(
    anno: type,
    name: str,
    type_to_converter: typing.Dict[type, typing.Type[converters.MolterConverter]],
) -> typing.Callable[[context.MolterContext, str], typing.Any]:  # type: ignore
    if typing_extensions.get_origin(anno) == typing_extensions.Annotated:
        anno = _get_from_anno_type(anno)

    if isinstance(anno, converters.MolterConverter):
        return _get_converter_function(anno, name)

    elif converter := type_to_converter.get(anno, None):
        return _get_converter_function(converter, name)

    elif typing_extensions.get_origin(anno) is typing.Literal:
        literals = typing_extensions.get_args(anno)
        return converters._LiteralConverter(literals).convert

    elif inspect.isfunction(anno):
        num_params = len(inspect.signature(anno).parameters.values())
        if num_params == 0:
            ValueError(
                f"{_get_name(anno)} for {name} has 0 arguments, which is unsupported."
            )
        elif num_params == 1:
            return lambda ctx, arg: anno(arg)
        elif num_params == 2:
            return lambda ctx, arg: anno(ctx, arg)
        else:
            ValueError(
                f"{_get_name(anno)} for {name} has more than 2 arguments, which is"
                " unsupported."
            )

    elif anno == bool:
        return lambda ctx, arg: _convert_to_bool(arg)

    elif anno == inspect._empty:
        return lambda ctx, arg: str(arg)

    else:
        return lambda ctx, arg: anno(arg)


_INVALID_GREEDY_TYPES = {NoneType, str, converters.Greedy}.union(UNION_TYPES)


def _greedy_parse(greedy: converters.Greedy, param: inspect.Parameter):
    default = param.default

    if param.kind in {param.KEYWORD_ONLY, param.VAR_POSITIONAL}:
        raise ValueError("Greedy[...] cannot be a variable or keyword-only argument.")

    arg = typing_extensions.get_args(greedy)[0]

    if typing_extensions.get_origin(arg) == typing_extensions.Annotated:
        arg = _get_from_anno_type(arg)

    if typing.get_origin(arg) in UNION_TYPES:
        args = typing.get_args(arg)

        if len(args) > 2 or NoneType not in args:
            raise ValueError(f"Greedy[{repr(arg)}] is invalid.")

        arg = args[0]
        default = None

    if arg in _INVALID_GREEDY_TYPES:
        raise ValueError(f"Greedy[{_get_name(arg)}] is invalid.")

    return arg, default


def _get_params(
    signature: inspect.Signature,
    type_to_converter: typing.Dict[type, typing.Type[converters.MolterConverter]],
    parameter_info: typing.Dict[str, ParameterInfo],
):
    cmd_params: list[PrefixedCommandParameter] = []

    # this is used by keyword-only and variable args to make sure there isn't more than one of either
    # mind you, we also don't want one keyword-only and one variable arg either
    finished_params = False
    params = signature.parameters

    for name, param in params.items():
        if finished_params:
            raise ValueError("Cannot have multiple keyword-only or variable arguments.")

        cmd_param = PrefixedCommandParameter()
        cmd_param.name = name
        cmd_param.kind = param.kind
        cmd_param.type = anno = param.annotation

        if parameter_dict := parameter_info.pop(name, None):
            cmd_param.default = parameter_dict["default"]
        else:
            cmd_param.default = (
                param.default
                if param.default is not param.empty
                else interactions.MISSING
            )

        if typing_extensions.get_origin(anno) == converters.Greedy:
            anno, default = _greedy_parse(anno, param)

            if default is not param.empty:
                cmd_param.default = default

        if typing_extensions.get_origin(anno) in UNION_TYPES:
            cmd_param.union = True
            for arg in typing_extensions.get_args(anno):
                if isinstance(anno, converters.NoArgumentConverter) or issubclass(
                    type_to_converter.get(anno, object), converters.NoArgumentConverter
                ):
                    cmd_param.no_argument = True

                if arg != NoneType:
                    converter = _get_converter(arg, name, type_to_converter)
                    cmd_param.converters.append(converter)
                elif not cmd_param.optional:  # d.py-like behavior
                    cmd_param.default = None
        else:
            if isinstance(anno, converters.NoArgumentConverter) or issubclass(
                type_to_converter.get(anno, object), converters.NoArgumentConverter
            ):
                cmd_param.no_argument = True

            converter = _get_converter(anno, name, type_to_converter)  # type: ignore
            cmd_param.converters.append(converter)

        if param.kind == param.KEYWORD_ONLY:
            if cmd_param.greedy:
                raise ValueError("Keyword-only arguments cannot be Greedy.")

            cmd_param.consume_rest = True
            finished_params = True
        elif param.kind == param.VAR_POSITIONAL:
            if cmd_param.optional:
                # there's a lot of parser ambiguities here, so i'd rather not
                raise ValueError(
                    "Variable arguments cannot have default values or be Optional."
                )
            if cmd_param.greedy:
                raise ValueError("Variable arguments cannot be Greedy.")

            cmd_param.variable = True
            finished_params = True

        cmd_params.append(cmd_param)

    if parameter_info:
        for name in parameter_info.keys():
            # this should only raise once due to how errors work
            raise ValueError(f'"{name}" is not a parameter in the command provided.')

    return cmd_params


async def _convert(
    param: PrefixedCommandParameter, ctx: context.MolterContext, arg: str
):
    converted = interactions.MISSING
    for converter in param.converters:
        try:
            converted = await maybe_coroutine(converter, ctx, arg)
            break
        except Exception as e:
            if not param.union and not param.optional:
                if isinstance(e, errors.BadArgument):
                    raise
                raise errors.BadArgument(str(e)) from e

    used_default = False
    if converted == interactions.MISSING:
        if param.optional:
            converted = (
                await maybe_coroutine(param.default, ctx)
                if inspect.isfunction(param.default)
                else param.default
            )
            used_default = True
        else:
            union_types = typing_extensions.get_args(param.type)
            union_names = tuple(_get_name(t) for t in union_types)
            union_types_str = ", ".join(union_names[:-1]) + f", or {union_names[-1]}"
            raise errors.BadArgument(
                f'Could not convert "{arg}" into {union_types_str}.'
            )

    if param.no_argument:
        # tells converter not to eat the current argument
        used_default = True

    return converted, used_default


async def _greedy_convert(
    param: PrefixedCommandParameter,
    ctx: context.MolterContext,
    args: _PrefixedArgsIterator,
):
    args.back()
    broke_off = False
    greedy_args = []

    for arg in args:
        try:
            greedy_arg, used_default = await _convert(param, ctx, arg)

            if used_default:
                raise errors.BadArgument()  # does it matter?

            greedy_args.append(greedy_arg)
        except errors.BadArgument:
            broke_off = True
            break

    if not greedy_args:
        if param.optional:
            greedy_args = (
                await maybe_coroutine(param.default, ctx)
                if inspect.isfunction(param.default)
                else param.default
            )
        else:
            raise errors.BadArgument(
                f"Failed to find any arguments for {repr(param.type)}."
            )

    return greedy_args, broke_off


@attrs.define(
    slots=True,
    kw_only=True,
    hash=False,
)
class MolterCommand:
    extension: typing.Optional["MolterExtension"] = attrs.field(default=None)
    "The extension this command belongs to."
    enabled: bool = attrs.field(default=True)
    "Whether this can be run at all."
    callback: typing.Callable[..., typing.Coroutine] = attrs.field(
        default=None,
    )
    "The coroutine to be called for this command"
    name: str = attrs.field()
    "The name of the command."

    parameters: typing.List[PrefixedCommandParameter] = attrs.field(factory=list)
    "The paramters of the command."
    aliases: typing.List[str] = attrs.field(
        factory=list,
    )
    "The list of aliases the command can be invoked under."
    hidden: bool = attrs.field(
        default=False,
    )
    "If `True`, the default help command does not show this in the help output."
    ignore_extra: bool = attrs.field(default=True)
    """
    If `True`, ignores extraneous strings passed to a command if all its
    requirements are met (e.g. ?foo a b c when only expecting a and b).
    Otherwise, an error is raised. Defaults to True.
    """
    hierarchical_checking: bool = attrs.field(default=True)
    """If `True` and if the base of a subcommand, every subcommand underneath
    it will run this command's checks and cooldowns before its own. Otherwise,
    only the subcommand's checks are checked."""

    help: typing.Optional[str] = attrs.field(default=None)
    """The long help text for the command."""
    brief: typing.Optional[str] = attrs.field(default=None)
    "The short help text for the command."
    parent: typing.Optional[typing_extensions.Self] = attrs.field(
        default=None,
    )
    "The parent command, if applicable."
    subcommands: typing.Dict[str, typing_extensions.Self] = attrs.field(
        factory=dict,
    )
    "A dict of all subcommands for the command."

    checks: typing.List[
        typing.Callable[
            [context.MolterContext], typing.Coroutine[typing.Any, typing.Any, bool]
        ]
    ] = attrs.field(factory=list)
    """A list of checks for this command."""
    error_callback: typing.Optional[ERROR_HANDLER_FUNCTION] = attrs.field(default=None)
    """The callback to use if an error occurs."""

    _usage: typing.Optional[str] = attrs.field(default=None, repr=False)
    _type_to_converter: typing.Dict[
        type, typing.Type[converters.MolterConverter]
    ] = attrs.field(factory=dict, converter=_merge_converters, repr=False)
    _parameter_info: typing.Dict[str, ParameterInfo] = attrs.field(
        factory=dict, repr=False
    )
    _signature: typing.Optional[inspect.Signature] = attrs.field(
        default=None, repr=False
    )

    def __attrs_post_init__(self) -> None:
        # for some reason, i can't seem to pick this up anywhere else
        if hasattr(self.callback, "_parameter_info"):
            self._parameter_info = self.callback._parameter_info

        # we have to do this afterwards as these rely on the callback
        # and its own value, which is impossible to get with attrs
        # methods, i think

        if self.help:
            self.help = inspect.cleandoc(self.help)
        else:
            self.help = inspect.getdoc(self.callback)
            if isinstance(self.help, bytes):
                self.help = self.help.decode("utf-8")

        if self.brief is None:
            self.brief = self.help.splitlines()[0] if self.help is not None else None

        if hasattr(self.callback, "__checks__"):
            self.checks = self.callback.__checks__

    def __hash__(self):
        return id(self)

    @property
    def usage(self) -> str:
        """
        A string displaying how the command can be used.
        If no string is set, it will default to the command's signature.
        Useful for help commands.
        """
        return self._usage or self.signature

    @usage.setter
    def usage(self, usage: str) -> None:
        self._usage = usage

    @property
    def qualified_name(self) -> str:
        """Returns the full qualified name of this command."""
        name_deq = collections.deque()
        command = self

        while command.parent is not None:
            name_deq.appendleft(command.name)
            command = command.parent

        name_deq.appendleft(command.name)
        return " ".join(name_deq)

    @property
    def all_commands(self) -> typing.FrozenSet[typing_extensions.Self]:
        """Returns all unique subcommands underneath this command."""
        return frozenset(self.subcommands.values())

    @property
    def signature(self) -> str:
        """Returns a POSIX-like signature useful for help command output."""
        if not self.parameters:
            return ""

        results = []

        for param in self.parameters:
            anno = param.type
            name = param.name

            if typing_extensions.get_origin(anno) == typing_extensions.Annotated:
                # prefixed commands can only have two arguments in an annotation anyways
                anno = _get_from_anno_type(anno)

            if not param.greedy and param.union:
                union_args = typing_extensions.get_args(anno)
                if len(union_args) == 2 and param.optional:
                    anno = union_args[0]

            if typing_extensions.get_origin(anno) is typing.Literal:
                # it's better to list the values it can be than display the variable name itself
                name = "|".join(
                    f'"{v}"' if isinstance(v, str) else str(v)
                    for v in typing_extensions.get_args(anno)
                )

            # we need to do a lot of manipulations with the signature
            # string, so using a deque as a string builder makes sense for performance
            result_builder: typing.Deque[str] = collections.deque()

            if param.optional and param.default is not None:
                # it would be weird making it look like name=None
                result_builder.append(f"{name}={param.default}")
            else:
                result_builder.append(name)

            if param.variable:
                # this is inside the brackets
                result_builder.append("...")

            # surround the result with brackets
            if param.optional:
                result_builder.appendleft("[")
                result_builder.append("]")
            else:
                result_builder.appendleft("<")
                result_builder.append(">")

            if param.greedy:
                # this is outside the brackets, making it differentiable from
                # a variable argument
                result_builder.append("...")

            results.append("".join(result_builder))

        return " ".join(results)

    def _parse_parameters(self) -> None:
        """
        Parses the parameters that this command has into a form molter can use.

        This is purposely seperated like this to allow "lazy parsing" - parsing
        as the command is added to a client rather than being parsed immediately.
        This allows variables like "self" to be filtered out, and allows
        for decorators that modify parameters to be parsed later, all at once.

        This is called automatically if you add the command via
        `MolterManager.add_prefixed_command`, but it is up to the user to remember
        to put the extension in, if needed.
        """

        if not self._signature:
            # we want to avoid ctx - self should have been handled earlier
            callback = functools.partial(self.callback, None)
            self._signature = inspect.signature(callback)

        # doing this here just so we don't run into any issues here with a value
        # not being there yet or something if we used defaults, idk
        self.parameters = _get_params(
            self._signature,
            self._type_to_converter,
            self._parameter_info,
        )

    def is_subcommand(self) -> bool:
        """Returns if this command is a subcommand or not."""
        return bool(self.parent)

    def add_command(self, cmd: typing_extensions.Self) -> None:
        """
        Adds a command as a subcommand to this command.

        Args:
            cmd (`MolterCommand`): The command to add
        """
        cmd.parent = self  # just so we know this is a subcommand

        if self.subcommands.get(cmd.name):
            raise ValueError(
                "Duplicate command! Multiple commands share the name/alias:"
                f" {self.qualified_name} {cmd.name}."
            )
        self.subcommands[cmd.name] = cmd

        for alias in cmd.aliases:
            if self.subcommands.get(alias):
                raise ValueError(
                    "Duplicate command! Multiple commands share the name/alias:"
                    f" {self.qualified_name} {cmd.name}."
                )
            self.subcommands[alias] = cmd

    def remove_command(self, name: str) -> None:
        """
        Removes a command as a subcommand from this command if it exists.
        If an alias is specified, only the alias will be removed.

        Args:
            name (`str`): The command to remove.
        """
        command = self.subcommands.pop(name, None)

        if command is None:
            return

        if name in command.aliases:
            command.aliases.remove(name)
            return

        for alias in command.aliases:
            self.subcommands.pop(alias, None)

    def get_command(self, name: str) -> typing.Optional[typing_extensions.Self]:
        """
        Gets a subcommand from this command. Can get subcommands of subcommands if needed.
        Args:
            name (`str`): The command to search for.
        Returns:
            `MolterCommand`: The command object, if found.
        """
        if " " not in name:
            return self.subcommands.get(name)

        names = name.split()
        if not names:
            return None

        cmd = self.subcommands.get(names[0])
        if not cmd or not cmd.subcommands:
            return cmd

        for name in names[1:]:
            try:
                cmd = cmd.subcommands[name]
            except (AttributeError, KeyError):
                return None

        return cmd

    @typing.overload
    def error(self) -> typing.Callable[[EHF], EHF]:
        ...

    @typing.overload
    def error(self, error_callback: EHF) -> EHF:
        ...

    def error(
        self,
        error_callback: typing.Optional[EHF] = None,
    ) -> typing.Union[typing.Callable[[EHF], EHF], EHF]:
        """
        A decorator to register an error callback for a command.

        Args:
            error_callback (`Callable`):
            The error callback to register. It must be an asynchronous function that
            takes in MolterContext and an exception.
        """

        def decorator(error_callback: EHF):
            self.error_callback = error_callback
            return error_callback

        if error_callback is not None:
            self.error_callback = error_callback
            return error_callback  # type: ignore

        return decorator

    def subcommand(
        self,
        name: typing.Optional[str] = None,
        *,
        aliases: typing.Optional[typing.List[str]] = None,
        help: typing.Optional[str] = None,
        brief: typing.Optional[str] = None,
        usage: typing.Optional[str] = None,
        enabled: bool = True,
        hidden: bool = False,
        ignore_extra: bool = True,
        hierarchical_checking: bool = True,
        type_to_converter: typing.Optional[
            typing.Dict[type, typing.Type[converters.MolterConverter]]
        ] = None,
    ) -> typing.Callable[..., typing_extensions.Self]:
        """
        A decorator to declare a subcommand for a molter prefixed command.

        Parameters:
            name (`str`, optional): The name of the command.
            Defaults to the name of the coroutine.

            aliases (`list[str]`, optional): The list of aliases the
            command can be invoked under.

            help (`str`, optional): The long help text for the command.
            Defaults to the docstring of the coroutine, if there is one.

            brief (`str`, optional): The short help text for the command.
            Defaults to the first line of the help text, if there is one.

            usage(`str`, optional): A string displaying how the command
            can be used. If no string is set, it will default to the
            command's signature. Useful for help commands.

            enabled (`bool`, optional): Whether this command can be run
            at all. Defaults to True.

            hidden (`bool`, optional): If `True`, the default help
            command (when it is added) does not show this in the help
            output. Defaults to False.

            ignore_extra (`bool`, optional): If `True`, ignores extraneous
            strings passed to a command if all its requirements are met
            (e.g. ?foo a b c when only expecting a and b).
            Otherwise, an error is raised. Defaults to True.

            hierarchical_checking (`bool`, optional): If `True` and if the
            base of a subcommand, every subcommand underneath it will run this
            command's checks before its own. Otherwise, only the subcommand's
            checks are checked. Defaults to True.

            type_to_converter (`dict[type, type[MolterConverter]]`, optional): A dict
            that associates converters for types. This allows you to use
            native type annotations without needing to use `typing.Annotated`.
            If this is not set, only interactions.py classes will be converted using
            built-in converters.

        Returns:
            `molter.MolterCommand`: The command object.
        """

        def wrapper(func):
            cmd = MolterCommand(  # type: ignore
                callback=func,
                name=name or func.__name__,
                aliases=aliases or [],
                help=help,
                brief=brief,
                usage=usage,  # type: ignore
                enabled=enabled,
                hidden=hidden,
                ignore_extra=ignore_extra,
                hierarchical_checking=hierarchical_checking,
                type_to_converter=type_to_converter  # type: ignore
                or getattr(func, "_type_to_converter", {}),
            )
            self.add_command(cmd)
            return cmd

        return wrapper

    async def _run_checks(self, ctx: context.MolterContext) -> None:
        for c in self.checks:
            try:
                if not await c(ctx):
                    raise errors.CheckFailure(ctx, check=c)
            except errors.CheckFailure as e:
                # pass in check function
                raise errors.CheckFailure(ctx, e.message, check=c)

    async def __call__(self, ctx: context.MolterContext) -> None:
        """
        Runs the command with checks.

        Args:
            ctx (`context.MolterContext`): The context to use for this command.
        """
        await self._run_checks(ctx)
        return await self.invoke(ctx)

    async def invoke(self, ctx: context.MolterContext) -> None:
        """
        Runs the callback of this command.

        Args:
            ctx (`context.MolterContext`): The context to use for this command.
        """
        # sourcery skip: remove-empty-nested-block, remove-redundant-if, remove-unnecessary-else
        callback = self.callback

        if len(self.parameters) == 0:
            return await callback(ctx)
        else:
            new_args: list[typing.Any] = []
            kwargs: dict[str, typing.Any] = {}
            args = _PrefixedArgsIterator(tuple(ctx.args))
            param_index = 0

            for arg in args:
                while param_index < len(self.parameters):
                    param = self.parameters[param_index]

                    if param.consume_rest:
                        arg = args.consume_rest()

                    if param.variable:
                        args_to_convert = args.get_rest_of_args()
                        new_arg = [
                            await _convert(param, ctx, arg) for arg in args_to_convert
                        ]
                        new_arg = tuple(arg[0] for arg in new_arg)
                        new_args.extend(new_arg)
                        param_index += 1
                        break

                    if param.greedy:
                        greedy_args, broke_off = await _greedy_convert(param, ctx, args)

                        new_args.append(greedy_args)
                        param_index += 1
                        if broke_off:
                            args.back()

                        if param.default:
                            continue
                        else:
                            break

                    converted, used_default = await _convert(param, ctx, arg)
                    if param.kind in {
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.VAR_POSITIONAL,
                    }:
                        new_args.append(converted)
                    else:
                        kwargs[param.name] = converted
                    param_index += 1

                    if not used_default:
                        break

            if param_index < len(self.parameters):
                for param in self.parameters[param_index:]:
                    if param.no_argument:
                        converted, _ = await _convert(param, ctx, None)  # type: ignore
                        if param.kind in {
                            inspect.Parameter.POSITIONAL_ONLY,
                            inspect.Parameter.VAR_POSITIONAL,
                        }:
                            new_args.append(converted)
                        else:
                            kwargs[param.name] = converted
                            break
                        continue

                    if not param.optional:
                        raise errors.BadArgument(
                            f"{param.name} is a required argument that is missing."
                        )
                    else:
                        default = (
                            await maybe_coroutine(param.default, ctx)
                            if inspect.isfunction(param.default)
                            else param.default
                        )

                        if param.kind in {
                            inspect.Parameter.POSITIONAL_ONLY,
                            inspect.Parameter.VAR_POSITIONAL,
                        }:
                            new_args.append(default)
                        else:
                            kwargs[param.name] = default
                            break
            elif not self.ignore_extra and not args.finished:
                raise errors.BadArgument(f"Too many arguments passed to {self.name}.")

            return await callback(ctx, *new_args, **kwargs)


def prefixed_command(
    name: typing.Optional[str] = None,
    *,
    aliases: typing.Optional[typing.List[str]] = None,
    help: typing.Optional[str] = None,
    brief: typing.Optional[str] = None,
    usage: typing.Optional[str] = None,
    enabled: bool = True,
    hidden: bool = False,
    ignore_extra: bool = True,
    hierarchical_checking: bool = True,
    type_to_converter: typing.Optional[
        typing.Dict[type, typing.Type[converters.MolterConverter]]
    ] = None,
) -> typing.Callable[..., MolterCommand]:
    """
    A decorator to declare a coroutine as a molter prefixed command.

    Parameters:
        name (`str`, optional): The name of the command.
        Defaults to the name of the coroutine.

        aliases (`list[str]`, optional): The list of aliases the
        command can be invoked under.

        help (`str`, optional): The long help text for the command.
        Defaults to the docstring of the coroutine, if there is one.

        brief (`str`, optional): The short help text for the command.
        Defaults to the first line of the help text, if there is one.

        usage(`str`, optional): A string displaying how the command
        can be used. If no string is set, it will default to the
        command's signature. Useful for help commands.

        enabled (`bool`, optional): Whether this command can be run
        at all. Defaults to True.

        hidden (`bool`, optional): If `True`, the default help
        command (when it is added) does not show this in the help
        output. Defaults to False.

        ignore_extra (`bool`, optional): If `True`, ignores extraneous
        strings passed to a command if all its requirements are met
        (e.g. ?foo a b c when only expecting a and b).
        Otherwise, an error is raised. Defaults to True.

        hierarchical_checking (`bool`, optional): If `True` and if the
        base of a subcommand, every subcommand underneath it will run this
        command's checks before its own. Otherwise, only the subcommand's
        checks are checked. Defaults to True.

        type_to_converter (`dict[type, type[MolterConverter]]`, optional): A dict
        that associates converters for types. This allows you to use
        native type annotations without needing to use `typing.Annotated`.
        If this is not set, only interactions.py classes will be converted using
        built-in converters.

    Returns:
        `molter.MolterCommand`: The command object.
    """

    def wrapper(func):
        return MolterCommand(  # type: ignore
            callback=func,
            name=name or func.__name__,
            aliases=aliases or [],
            help=help,
            brief=brief,
            usage=usage,  # type: ignore
            enabled=enabled,
            hidden=hidden,
            ignore_extra=ignore_extra,
            hierarchical_checking=hierarchical_checking,
            type_to_converter=type_to_converter  # type: ignore
            or getattr(func, "_type_to_converter", {}),
        )

    return wrapper


prefix_command = prefixed_command
text_command = prefixed_command
text_based_command = prefixed_command


# molter command typevar - can be the function or the command
MCT = typing.TypeVar("MCT", typing.Callable, MolterCommand)


def register_converter(
    type_: type, converter: typing.Type[converters.MolterConverter]
) -> typing.Callable[..., MCT]:
    """
    A decorator that allows you to register converters for a type for a specific command.
    This allows for native type annotations without needing to use `typing(_extensions).Annotated`.
    Args:
        type_ (`type`): The type to register for.
        converter (`type[MolterConverter]`): The converter to use for the type.
    Returns:
        `Callable | MolterCommand`: Either the callback or the command.
        If this is used after using the `molter.prefixed_command` decorator, it will be a command.
        Otherwise, it will be a callback.
    """
    if not isinstance(converter, converters.MolterConverter):
        raise ValueError('Converter provided did not have a "convert" method.')

    def wrapper(command: MCT) -> MCT:
        if hasattr(command, "_type_to_converter"):
            command._type_to_converter[type_] = converter
        else:
            command._type_to_converter = {type_: converter}

        return command

    return wrapper


def globally_register_converter(
    anno_type: type, converter: typing.Type[converters.MolterConverter]
) -> None:
    """
    A decorator that allows you to register converters for commands decorated/made after this is run.
    This allows for native type annotations without needing to use `typing.Annotated`.
    Note that this does not retroactively register converters for commands already made.
    Args:
        anno_type (`type`): The type to register for.
        converter (`type[MolterConverter]`): The converter to use for the type.
    """
    if not isinstance(converter, converters.MolterConverter):
        raise ValueError('Converter provided did not have a "convert" method.')

    # hate me, but i think it makes sense here
    global _global_type_to_converter
    _global_type_to_converter.update({anno_type: converter})


def prefixed_parameter(
    parameter_name: str,
    *,
    default: typing.Any = interactions.MISSING,
    factory: typing.Optional[
        typing.Callable[[context.MolterContext], typing.Any]
    ] = None,
) -> typing.Callable[..., MCT]:
    """
    A decorator that allows you to adjust a parameter in a prefixed comamnd.

    Args:
        parameter_name (`str`): The parameter in the command to edit.
        default (`Any`, optional): The default value the parameter should have.
        factory (`Callable[MolterContext]`, optional): A factory function to use
        if no argument is provided for this parameter. The function can be asynchronous
        or synchronous, and should take in solely a `MolterContext`.

    Returns:
        `Callable | MolterCommand`: Either the callback or the command.
        If this is used after using the `molter.prefixed_command` decorator, it will be a command.
        Otherwise, it will be a callback.
    """

    def wrapper(command: MCT) -> MCT:
        parameter_info: ParameterInfo = {}  # type: ignore

        if factory is not None and default is not interactions.MISSING:
            raise ValueError("You cannot provide both a default and a factory.")
        elif factory is None and default is interactions.MISSING:
            raise ValueError("You must provide either a default or a factory.")

        if factory is not None:
            parameter_info["default"] = factory
        elif default is not interactions.MISSING:
            parameter_info["default"] = default

        if hasattr(command, "_parameters_info"):
            command._parameter_info[parameter_name] = parameter_info  # type: ignore
        else:
            command._parameter_info = {parameter_name: parameter_info}  # type: ignore

        return command

    return wrapper


@typing.overload
def ext_error_handler() -> typing.Callable[[EEH], EEH]:
    ...


@typing.overload
def ext_error_handler(error_callback: EEH) -> EEH:
    ...


def ext_error_handler(
    error_callback: typing.Optional[EEH] = None,
) -> typing.Union[typing.Callable[[EEH], EEH], EEH]:
    """
    A decorator to register an error callback for a MolterExtension.

    Args:
        error_callback (`Callable`):
        The error callback to register. It must be an asynchronous function that
        takes in `self`, MolterContext and an exception.
    """

    def decorator(error_callback: EEH):
        error_callback.__ext_molter_error__ = True
        return error_callback

    if error_callback is not None:
        error_callback.__ext_molter_error__ = True
        return error_callback

    return decorator
