import functools
import inspect
import logging
import traceback
import typing

import interactions
from . import utils
from .command import MolterCommand
from .context import MolterContext
from .converters import MolterConverter
from interactions import ext

__all__ = (
    "__version__",
    "base",
    "MolterInjectedClient",
    "MolterExtension",
    "Molter",
    "setup",
)

__version__ = "0.4.1"

logger: logging.Logger = logging.getLogger("molter")


version = ext.Version(
    version=__version__,
    authors=[ext.VersionAuthor("Astrea49")],
)

base = ext.Base(
    name="interactions-molter",
    version=version,
    link="https://github.com/interactions-py/molter/",
    description=(
        "An extension library for interactions.py to add prefixed commands. Ported from"
        " dis-snek."
    ),
    packages=["interactions.ext.molter"],
    requirements=["discord-py-interactions>=4.1.0"],
)


class MolterInjectedClient(interactions.Client):
    """
    A semi-stub for Clients injected with Molter.
    This should only be used for typehinting.
    """

    molter: "Molter"


class MolterExtension(interactions.Extension):
    """An extension that allows you to use molter commands in them."""

    client: interactions.Client
    _molter_prefixed_commands: typing.List[MolterCommand]

    def __new__(
        cls, client: interactions.Client, *args, **kwargs
    ) -> "interactions.Extension":
        self: "MolterExtension" = super().__new__(cls, client, *args, **kwargs)  # type: ignore
        self._molter_prefixed_commands = []

        # typehinting funkyness for better typehints
        self.client = typing.cast(MolterInjectedClient, self.client)

        for _, cmd in inspect.getmembers(
            self, predicate=lambda x: isinstance(x, MolterCommand)
        ):
            cmd: MolterCommand

            if not cmd.is_subcommand():  # we don't want to add subcommands
                cmd.extension = self
                cmd.callback = functools.partial(cmd.callback, self)
                self._molter_prefixed_commands.append(cmd)
                self.client.molter.add_prefixed_command(cmd)

        return self

    async def teardown(self):
        # typehinting funkyness for better typehints
        self.client = typing.cast(MolterInjectedClient, self.client)

        for cmd in self._molter_prefixed_commands:
            names_to_remove = cmd.aliases.copy()
            names_to_remove.append(cmd.name)

            for name in names_to_remove:
                self.client.molter.prefixed_commands.pop(name, None)

        return await super().teardown()


class Molter:
    """
    The main part of the extension. Deals with injecting itself in the first place.

    Parameters:
        client (`interactions.Client`): The client instance.
        default_prefix (`str | typing.Iterable[str]`, optional): \
            The default prefix to use. Defaults to None.
        generate_prefixes (`typing.Callable`, optional): An asynchronous function \
            that takes in a `Client` and `Message` object and returns either a \
            string or an iterable of strings. Defaults to None.
        fetch_data_for_context (`bool`): If molter should attempt to fetch extra \
            data, like the `Guild` and `Channel` where the message was sent. \
            Turning this on may make the bot respond slower or faster depending on \
            the converters used in the command, but usually is slower. \
            Defaults to False.
        on_molter_command_error (`typing.Callable`, optional): An asynchronous function \
            that takes in a `MolterContext` and `Exception` to handle errors that occur \
            when running molter commands. By default, molter will output the error to \
            the default logging place and ignore it. The error event can also be listened \
            to by listening to the "on_molter_command_error" event.

        If neither `default_prefix` or `generate_prefixes` are provided, the bot
        defaults to using it being mentioned as its prefix.
    """

    def __init__(
        self,
        client: interactions.Client,
        default_prefix: typing.Optional[typing.Union[str, typing.Iterable[str]]] = None,
        generate_prefixes: typing.Optional[
            typing.Callable[
                [interactions.Client, interactions.Message],
                typing.Coroutine[
                    typing.Any, typing.Any, typing.Union[str, typing.Iterable[str]]
                ],
            ]
        ] = None,
        fetch_data_for_context: bool = False,
        on_molter_command_error: typing.Optional[
            typing.Callable[[MolterContext, Exception], typing.Coroutine]
        ] = None,
    ) -> None:

        # typehinting funkyness for better typehints
        client = typing.cast(MolterInjectedClient, client)

        self.client = client
        self.default_prefix = default_prefix
        self.fetch_data_for_context = fetch_data_for_context
        self.prefixed_commands: typing.Dict[str, MolterCommand] = {}

        if default_prefix is None and generate_prefixes is None:
            # by default, use mentioning the bot as the prefix
            generate_prefixes = utils.when_mentioned

        self.generate_prefixes = (  # type: ignore
            generate_prefixes
            if generate_prefixes is not None
            else self.generate_prefixes
        )
        self.on_molter_command_error = (  # type: ignore
            on_molter_command_error
            if on_molter_command_error is not None
            else self.on_molter_command_error
        )

        # this allows us to use a (hopefully) non-conflicting namespace
        self.client.molter = self

        self.client.event(self._handle_prefixed_commands, name="on_message_create")  # type: ignore
        self.client.event(self.on_molter_command_error, name="on_molter_command_error")  # type: ignore

    def add_prefixed_command(self, command: MolterCommand):
        """Add a prefixed command to the client.

        Args:
            command (`MolterCommand`): The command to add.
        """
        if command.parent:
            return  # silent return to ignore subcommands - hacky, ik

        if command.name not in self.prefixed_commands:
            self.prefixed_commands[command.name] = command
        else:
            raise ValueError(
                f"Duplicate Command! Multiple commands share the name {command.name}"
            )

        for alias in command.aliases:
            if alias not in self.prefixed_commands:
                self.prefixed_commands[alias] = command
                continue
            raise ValueError(
                f"Duplicate Command! Multiple commands share the name/alias {alias}"
            )

    def prefixed_command(
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
        type_to_converter: typing.Optional[
            typing.Dict[type, typing.Type[MolterConverter]]
        ] = None,
    ):
        """
        A decorator to declare a coroutine as a Molter prefixed command.

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

            type_to_converter (`dict[type, type[MolterConverter]]`, optional): A dict
            that associates converters for types. This allows you to use
            native type annotations without needing to use `typing.Annotated`.
            If this is not set, only dis-snek classes will be converted using
            built-in converters.

        Returns:
            `MolterCommand`: The command object.
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
                type_to_converter=type_to_converter  # type: ignore
                or getattr(func, "_type_to_converter", {}),
            )
            self.add_prefixed_command(cmd)
            return cmd

        return wrapper

    prefix_command = prefixed_command
    text_based_command = prefixed_command

    async def generate_prefixes(
        self, client: interactions.Client, msg: interactions.Message
    ) -> typing.Union[str, typing.Iterable[str]]:
        """
        Generates a list of prefixes a prefixed command can have based on the client and message.
        This can be overwritten by passing a function to generate_prefixes on initialization.

        Args:
            client (`interactions.Client`): The client instance.
            msg (`interactions.Message`): The message sent.

        Returns:
            `str` | `Iterable[str]`: The prefix(es) to check for.
        """
        return self.default_prefix  # type: ignore

    async def on_molter_command_error(self, context: MolterContext, error: Exception):
        """
        A function that is called when a molter command errors out.
        By default, this function outputs to the default logging place.

        Args:
            context (`MolterContext`): The context in which the error occured.
            error (`Exception`): The exception raised by the molter command.
        """

        out = traceback.format_exception(type(error), error, error.__traceback__)
        logger.error(
            "Ignoring exception in {}:{}{}".format(
                f"molter cmd / {context.invoked_name}",
                "\n" if len(out) > 1 else " ",
                "".join(out),
            ),
        )

    async def _create_context(self, msg: interactions.Message) -> MolterContext:
        """
        Creates a `MolterContext` object from the given message.

        Args:
            msg (`interactions.Message`): The message to create a context from.

        Returns:
            `MolterContext`: The context generated.
        """
        # weirdly enough, sometimes this isn't set right
        msg._client = self.client._http

        channel = None
        guild = None

        if self.fetch_data_for_context:
            # get from cache if possible
            channel = await msg.get_channel()
            if msg.guild_id:
                guild = await msg.get_guild()

        return MolterContext(  # type: ignore
            client=self.client,
            message=msg,
            user=msg.author,  # type: ignore
            member=msg.member,
            channel=channel,
            guild=guild,
        )

    async def _handle_prefixed_commands(self, msg: interactions.Message):
        """
        Determines if a command is being triggered and dispatch it.

        Args:
            msg (`interactions.Message`): The message created.
        """

        if not msg.content or msg.author.bot:
            return

        prefixes = await self.generate_prefixes(self.client, msg)

        if isinstance(prefixes, str):
            # its easier to treat everything as if it may be an iterable
            # rather than building a special case for this
            prefixes = (prefixes,)

        if prefix_used := next(
            (prefix for prefix in prefixes if msg.content.startswith(prefix)), None
        ):
            context = await self._create_context(msg)
            context.prefix = prefix_used
            context.content_parameters = utils.remove_prefix(msg.content, prefix_used)
            command: typing.Optional[
                typing.Union[Molter, MolterCommand]
            ] = self.client.molter

            while True:
                first_word: str = utils.get_first_word(context.content_parameters)  # type: ignore
                if isinstance(command, MolterCommand):
                    new_command = command.subcommands.get(first_word)
                else:
                    new_command = command.prefixed_commands.get(first_word)
                if not new_command or not new_command.enabled:
                    break

                command = new_command
                context.content_parameters = utils.remove_prefix(
                    context.content_parameters, first_word
                ).strip()

            if isinstance(command, Molter):
                command = None

            if command and command.enabled:
                # this looks ugly, ik
                context.invoked_name = utils.remove_suffix(
                    utils.remove_prefix(msg.content, prefix_used),
                    context.content_parameters,
                ).strip()
                context.args = utils.get_args_from_str(context.content_parameters)
                context.command = command

                try:
                    await command(context)
                except Exception as e:
                    self.client._websocket._dispatch.dispatch(
                        "on_molter_command_error", context, e
                    )


def setup(
    client: interactions.Client,
    default_prefix: typing.Optional[typing.Union[str, typing.Iterable[str]]] = None,
    generate_prefixes: typing.Optional[
        typing.Callable[
            [interactions.Client, interactions.Message],
            typing.Coroutine[
                typing.Any, typing.Any, typing.Union[str, typing.Iterable[str]]
            ],
        ]
    ] = None,
    fetch_data_for_context: bool = False,
    on_molter_command_error: typing.Optional[
        typing.Callable[[MolterContext, Exception], typing.Coroutine]
    ] = None,
    *args,
    **kwargs,
) -> Molter:
    """
    Allows setup of Molter through normal extension loaded.

    Parameters:
        client (`interactions.Client`): The client instance.
        default_prefix (`str | typing.Iterable[str]`, optional): \
            The default prefix to use. Defaults to None.
        generate_prefixes (`typing.Callable`, optional): An asynchronous function \
            that takes in a `Client` and `Message` object and returns either a \
            string or an iterable of strings. Defaults to None.
        fetch_data_for_context (`bool`): If molter should attempt to fetch extra \
            data, like the `Guild` and `Channel` where the message was sent. \
            Turning this on may make the bot respond slower or faster depending on \
            the converters used in the command, but usually is slower. \
            Defaults to False.
        on_molter_command_error (`typing.Callable`, optional): An asynchronous function \
            that takes in a `MolterContext` and `Exception` to handle errors that occur \
            when running molter commands. By default, molter will output the error to \
            the default logging place and ignore it. The error event can also be listened \
            to by listening to the "on_molter_command_error" event.

        If neither `default_prefix` or `generate_prefixes` are provided, the bot
        defaults to using it being mentioned as its prefix.

    Returns:
        `Molter`: The class that deals with all things Molter.
    """
    return Molter(
        client,
        default_prefix,
        generate_prefixes,
        fetch_data_for_context,
        on_molter_command_error,
    )
