import functools
import inspect
import logging
import traceback
import typing
from hashlib import md5

import interactions
from . import utils
from .command import MolterCommand
from .context import MolterContext
from interactions import ext

__all__ = ("__version__", "base", "MolterExtension", "Molter", "setup")

__version__ = "0.3.1"

logger: logging.Logger = logging.getLogger("molter")


class VersionAuthorPatch(ext.VersionAuthor):
    def __init__(self, name, *, shared=False, active=True, email=None) -> None:
        self.name = name
        self._co_author = shared
        self.active = active
        self.email = email
        self._hash = md5(self.__str__().encode("utf-8"))


class VersionPatch(ext.Version):
    __slots__ = ("_major", "_minor", "_patch", "_authors", "__version", "__alphanum")


class BasePatch(ext.Base):
    __slots__ = (
        "_packages",
        "_requirements",
        "_kwargs",
        "__objects",
        "version",
        "name",
        "description",
        "long_description",
        "link",
    )


version = VersionPatch(
    version=__version__,
    authors=[VersionAuthorPatch("Astrea49")],
)

base = BasePatch(
    name="interactions-molter",
    version=version,
    link="https://github.com/interactions-py/molter/tree/main/examples",
    description=(
        "An extension library for interactions.py to add text-based commands. Ported"
        " from dis-snek."
    ),
    packages=["interactions.ext.molter"],
    requirements=["discord-py-interactions>=4.1.0"],
)


class MolterExtension(interactions.Extension):
    """An extension that allows you to use molter commands in them."""

    _msg_commands: typing.List[MolterCommand]

    def __new__(
        cls, client: interactions.Client, *args, **kwargs
    ) -> "interactions.Extension":
        self = super().__new__(cls, client, *args, **kwargs)
        self._msg_commands = []

        for _, cmd in inspect.getmembers(
            self, predicate=lambda x: isinstance(x, MolterCommand)
        ):
            cmd: MolterCommand

            if not cmd.parent:  # we don't want to add subcommands
                cmd.extension = self
                cmd.callback = functools.partial(cmd.callback, self)
                self._msg_commands.append(cmd)
                self.client.add_message_command(cmd)

        return self

    def teardown(self):
        for cmd in self._msg_commands:
            names_to_remove = cmd.aliases.copy()
            names_to_remove.append(cmd.name)

            for name in names_to_remove:
                self.client.msg_commands.pop(name, None)

        return super().teardown()


class Molter:
    """
    The main part of the extension. Deals with injecting itself in the first place.

    Parameters:
        bot (`interactions.Client`): The bot instance.
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
        bot: interactions.Client,
        default_prefix: typing.Union[str, typing.Iterable[str]] = None,
        generate_prefixes: typing.Callable[
            [interactions.Client, interactions.Message],
            typing.Coroutine[
                typing.Any, typing.Any, typing.Union[str, typing.Iterable[str]]
            ],
        ] = None,
        fetch_data_for_context: bool = False,
        on_molter_command_error: typing.Callable[
            [MolterContext, Exception], typing.Coroutine
        ] = None,
    ) -> None:

        self.bot = bot
        self.default_prefix = default_prefix
        self.fetch_data_for_context = fetch_data_for_context

        if default_prefix is None and generate_prefixes is None:
            # by default, use mentioning the bot as the prefix
            generate_prefixes = utils.when_mentioned

        self.generate_prefixes = (
            generate_prefixes
            if generate_prefixes is not None
            else self.generate_prefixes
        )
        self.on_molter_command_error = (
            on_molter_command_error
            if on_molter_command_error is not None
            else self.on_molter_command_error
        )

        self.bot.msg_commands = {}
        self.bot.add_message_command = self.add_message_command

        self.bot.event(self._handle_msg_commands, "on_message_create")
        self.bot.event(self.on_molter_command_error, "on_molter_command_error")

    def add_message_command(self, command: MolterCommand):
        """Add a message command to the client.
        This method gets monkeypatched into the client when molter is initialized.

        Args:
            command (`MolterCommand`): The command to add.
        """
        if command.parent:
            return  # silent return to ignore subcommands - hacky, ik

        if command.name not in self.bot.msg_commands:
            self.bot.msg_commands[command.name] = command
        else:
            raise ValueError(
                f"Duplicate Command! Multiple commands share the name {command.name}"
            )

        for alias in command.aliases:
            if alias not in self.bot.msg_commands:
                self.bot.msg_commands[alias] = command
                continue
            raise ValueError(
                f"Duplicate Command! Multiple commands share the name/alias {alias}"
            )

    def message_command(
        self,
        name: str = None,
        *,
        aliases: typing.List[str] = None,
        help: str = None,
        brief: str = None,
        usage: str = None,
        enabled: bool = True,
        hidden: bool = False,
        ignore_extra: bool = True,
    ):
        """
        A decorator to declare a coroutine as a Molter message command.

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
            )
            self.bot.add_message_command(cmd)
            return cmd

        return wrapper

    msg_command = message_command
    prefix_command = message_command
    text_based_command = message_command

    async def generate_prefixes(
        self, bot: interactions.Client, msg: interactions.Message
    ):
        """
        Generates a list of prefixes a message command can have based on the bot and message.
        This can be overwritten by passing a function to generate_prefixes on initialization.

        Args:
            bot (`interactions.Client`): The bot instance.
            msg (`interactions.Message`): The message sent.

        Returns:
            `str` | `Iterable[str]`: The prefix(es) to check for.
        """
        return self.default_prefix

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
        msg._client = self.bot._http  # weirdly enough, sometimes this isn't set right

        channel = None
        guild = None

        if self.fetch_data_for_context:
            # get from cache if possible
            channel = await msg.get_channel()
            if msg.guild_id:
                guild = await msg.get_guild()

        return MolterContext(  # type: ignore
            client=self.bot,
            message=msg,
            user=msg.author,
            member=msg.member,
            channel=channel,
            guild=guild,
        )

    async def _handle_msg_commands(self, msg: interactions.Message):
        """
        Determines if a command is being triggered and dispatch it.

        Args:
            msg (`interactions.Message`): The message created.
        """

        if not msg.content or msg.author.bot:
            return

        prefixes = await self.generate_prefixes(self.bot, msg)

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
            command = self.bot

            while True:
                first_word: str = utils.get_first_word(context.content_parameters)  # type: ignore
                if isinstance(command, MolterCommand):
                    new_command = command.command_dict.get(first_word)
                else:
                    new_command = command.msg_commands.get(first_word)
                if not new_command or not new_command.enabled:
                    break

                command = new_command
                context.content_parameters = utils.remove_prefix(
                    context.content_parameters, first_word
                ).strip()

            if isinstance(command, interactions.Client):
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
                    self.bot._websocket._dispatch.dispatch(
                        "on_molter_command_error", context, e
                    )


def setup(
    bot: interactions.Client,
    default_prefix: typing.Union[str, typing.Iterable[str]] = None,
    generate_prefixes: typing.Callable[
        [interactions.Client, interactions.Message],
        typing.Coroutine[
            typing.Any, typing.Any, typing.Union[str, typing.Iterable[str]]
        ],
    ] = None,
    fetch_data_for_context: bool = False,
    on_molter_command_error: typing.Callable[
        [MolterContext, Exception], typing.Coroutine
    ] = None,
    *args,
    **kwargs,
) -> None:
    """
    Allows setup of the bot.
    This method is not recommended - use `Molter` directly instead.
    """
    Molter(
        bot,
        default_prefix,
        generate_prefixes,
        fetch_data_for_context,
        on_molter_command_error,
    )
