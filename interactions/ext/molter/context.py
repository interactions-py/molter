import typing as _typing

import attrs

import interactions
from . import utils

if _typing.TYPE_CHECKING:
    from .command import MolterCommand
    from .base import MolterInjectedClient

__all__ = ("MolterContext",)


@attrs.define()
class MolterContext:
    """
    A special 'Context' object for `molter`'s commands.
    This does not actually inherit from `interactions._Context`.
    """

    client: "MolterInjectedClient" = attrs.field()
    """The bot instance."""
    message: interactions.Message = attrs.field()
    """The message this represents."""
    channel: interactions.Channel = attrs.field()
    """The channel this message was sent through."""
    user: interactions.User = attrs.field()
    """The user who sent the message."""

    member: _typing.Optional[interactions.Member] = attrs.field(default=None)
    """The guild member who sent the message, if applicable."""
    guild: _typing.Optional[interactions.Guild] = attrs.field(default=None)
    """The guild this message was sent through, if applicable."""

    invoked_name: str = attrs.field(init=False, default=None)
    """The name/alias used to invoke the command."""
    content_parameters: str = attrs.field(init=False, default=None)
    """The message content without the prefix or command."""
    command: "MolterCommand" = attrs.field(init=False, default=None)
    """The command invoked."""
    args: _typing.List[_typing.Any] = attrs.field(init=False, factory=list)
    """The arguments used for this command."""
    prefix: str = attrs.field(default=None)
    """The prefix used for this command."""

    extras: _typing.Dict[_typing.Any, _typing.Any] = attrs.field(
        init=False, factory=dict, repr=False
    )
    """Extras used for this context. These can contain your own custom data."""

    _guild_permissions: _typing.Optional[interactions.Permissions] = attrs.field(
        init=False,
        default=None,
        repr=False,
    )
    _channel_permissions: _typing.Optional[interactions.Permissions] = attrs.field(
        init=False,
        default=None,
        repr=False,
    )

    def __attrs_post_init__(self) -> None:
        for inter_object in (
            self.message,
            self.member,
            self.channel,
            self.guild,
        ):
            if (
                not inter_object
                or inter_object is interactions.MISSING
                or "_client" not in inter_object.__slots__  # type: ignore
            ):
                continue
            inter_object._client = self._http

        if self.member:
            # discord doesn't provide this field normally with messages, but
            # we can easily add it here for convenience
            self.member.user = self.user

    @property
    def author(self) -> _typing.Union[interactions.Member, interactions.User]:
        """
        Either the member or user who sent the message. Prefers member,
        but defaults to user if the member does not exist.
        This is useful for getting a Discord user, regardless of if the
        message was from a guild or not.

        This is different from both the API and interactions.py in that
        this can be a member object. It follows the conventions of other
        Python Discord libraries.
        """
        return self.member or self.user

    @property
    def me(self) -> _typing.Union[interactions.Member, interactions.User, None]:
        """Returns the bot member or user, if cached."""
        if not self.client.me:
            return None

        if not self.guild:
            return interactions.get(
                self.client,
                interactions.User,
                object_id=int(self.client.me.id),
                force="cache",
            )

        return interactions.get(
            self.client,
            interactions.Member,
            parent_id=int(self.guild.id),
            object_id=int(self.client.me.id),
            force="cache",
        )

    @property
    def bot(self) -> interactions.Client:
        """An alias to `MolterContext.client`."""
        return self.client

    @property
    def channel_id(self) -> interactions.Snowflake:
        """Returns the channel ID where the message was sent."""
        return self.message.channel_id  # type: ignore

    @property
    def guild_id(self) -> _typing.Optional[interactions.Snowflake]:
        """Returns the guild ID where the message was sent, if applicable."""
        return self.message.guild_id

    @property
    def _http(self) -> interactions.HTTPClient:
        """Returns the HTTP client the client has."""
        return self.client._http

    @property
    def bot_permissions(self) -> _typing.Optional[interactions.Permissions]:
        """
        Returns the permissions the bot has for this context, if the bot user is cached.

        This factors in ownership, roles, and channel overwrites.
        This does not take into account implicit permissions.
        """
        return utils.permissions(self.me, self.channel, self.guild) if self.me else None

    @property
    def author_permissions(self) -> interactions.Permissions:
        """
        Returns the permissions the sender of this context has.

        This factors in ownership, roles, and channel overwrites.
        This does not take into account implicit permissions.
        """
        return utils.permissions(self.author, self.channel, self.guild)

    @property
    def _sendable_channel(self) -> interactions.Channel:
        """
        Gets the channel to send a message for.
        We don't exactly need a channel with fully correct attributes,
        so we can use a dummy channel here.
        """
        return self.channel or interactions.Channel(
            id=self.channel_id, type=0, _client=self._http  # type: ignore
        )

    def typing(self) -> utils.Typing:
        """
        A context manager to send a typing state to a given channel
        as long as long as the wrapped operation takes.

        Usage:

        ```python
        async with ctx.typing():
            # do stuff here
        ```
        """
        return utils.Typing(self._http, int(self.channel_id))

    async def fetch_me(self) -> _typing.Union[interactions.Member, interactions.User]:
        """
        Fetches the bot member or user.

        This is more reliable than `MolterContext.me` as it can
        fetch data from Discord if needed.
        """
        if not self.client.me:
            raise ValueError("You must be logged in to use this.")

        if self.guild:
            return await interactions.get(
                self.client,
                interactions.Member,
                parent_id=int(self.guild.id),
                object_id=int(self.client.me.id),
            )
        else:
            return await interactions.get(
                self.client,
                interactions.User,
                object_id=int(self.client.me.id),
            )

    async def fetch_bot_permissions(self) -> interactions.Permissions:
        """
        Fetches the permissions the bot has for this context.

        This factors in ownership, roles, and channel overwrites.
        This does not take into account implicit permissions.

        This is more reliable than `MolterContext.bot_permissions`
        as it can fetch data from Discord if needed.
        """

        me = await self.fetch_me()
        return utils.permissions(me, self.channel, self.guild)

    async def send(
        self,
        content: _typing.Optional[str] = interactions.MISSING,  # type: ignore
        *,
        tts: _typing.Optional[bool] = interactions.MISSING,  # type: ignore
        files: _typing.Optional[
            _typing.Union[interactions.File, _typing.List[interactions.File]]
        ] = interactions.MISSING,  # type: ignore
        embeds: _typing.Optional[
            _typing.Union["interactions.Embed", _typing.List["interactions.Embed"]]
        ] = interactions.MISSING,  # type: ignore
        allowed_mentions: _typing.Optional[
            "interactions.MessageInteraction"
        ] = interactions.MISSING,  # type: ignore
        components: _typing.Optional[
            _typing.Union[
                "interactions.ActionRow",  # type: ignore
                "interactions.Button",  # type: ignore
                "interactions.SelectMenu",  # type: ignore
                _typing.List["interactions.ActionRow"],  # type: ignore
                _typing.List["interactions.Button"],  # type: ignore
                _typing.List["interactions.SelectMenu"],  # type: ignore
            ]
        ] = interactions.MISSING,  # type: ignore
        **kwargs,
    ) -> "interactions.Message":  # type: ignore
        """
        Sends a message in the channel where the message came from.

        Args:
            content (`str`, optional): The contents of the message as a string
            or string-converted value.

            tts (`bool`, optional): Whether the message utilizes the text-to-speech
            Discord programme or not.

            files (`interactions.File | list[interactions.File]`, optional):
            A file or list of files to be attached to the message.

            embeds (`interactions.Embed | list[interactions.Embed]`, optional):
            An embed, or list of embeds for the message.

            allowed_mentions (`interactions.MessageInteraction`, optional):
            The message interactions/mention limits that the message can refer to.

            components (`interactions.ActionRow | interactions.Button |
            interactions.SelectMenu | list[interactions.ActionRow] |
            list[interactions.Button] | list[interactions.SelectMenu]`, optional):
            A component, or list of components for the message.

        Returns:
            `interactions.Message`: The sent message as an object.
        """

        return await self._sendable_channel.send(
            content,
            tts=tts,
            files=files,
            embeds=embeds,
            allowed_mentions=allowed_mentions,
            components=components,  # type: ignore
            **kwargs,
        )

    async def reply(
        self,
        content: _typing.Optional[str] = interactions.MISSING,  # type: ignore
        *,
        tts: _typing.Optional[bool] = interactions.MISSING,  # type: ignore
        files: _typing.Optional[
            _typing.Union[interactions.File, _typing.List[interactions.File]]
        ] = interactions.MISSING,  # type: ignore
        embeds: _typing.Optional[
            _typing.Union["interactions.Embed", _typing.List["interactions.Embed"]]
        ] = interactions.MISSING,  # type: ignore
        allowed_mentions: _typing.Optional[
            "interactions.MessageInteraction"
        ] = interactions.MISSING,  # type: ignore
        components: _typing.Optional[
            _typing.Union[
                "interactions.ActionRow",  # type: ignore
                "interactions.Button",  # type: ignore
                "interactions.SelectMenu",  # type: ignore
                _typing.List["interactions.ActionRow"],  # type: ignore
                _typing.List["interactions.Button"],  # type: ignore
                _typing.List["interactions.SelectMenu"],  # type: ignore
            ]
        ] = interactions.MISSING,  # type: ignore
        **kwargs,
    ) -> "interactions.Message":  # type: ignore
        """
        Sends a new message replying to the old.

        Args:
            content (`str`, optional): The contents of the message as a string
            or string-converted value.

            tts (`bool`, optional): Whether the message utilizes the text-to-speech
            Discord programme or not.

            files (`interactions.File | list[interactions.File]`, optional):
            A file or list of files to be attached to the message.

            embeds (`interactions.Embed | list[interactions.Embed]`, optional):
            An embed, or list of embeds for the message.

            allowed_mentions (`interactions.MessageInteraction`, optional):
            The message interactions/mention limits that the message can refer to.

            components (`interactions.ActionRow | interactions.Button |
            interactions.SelectMenu | list[interactions.ActionRow] |
            list[interactions.Button] | list[interactions.SelectMenu]`, optional):
            A component, or list of components for the message.

        Returns:
            `interactions.Message`: The sent message as an object.
        """

        return await self.message.reply(
            content,
            tts=tts,
            files=files,
            embeds=embeds,
            allowed_mentions=allowed_mentions,
            components=components,  # type: ignore
            **kwargs,
        )
