import typing

import attrs

import interactions
from . import utils

if typing.TYPE_CHECKING:
    from .command import MolterCommand
    from .base import MolterInjectedClient

__all__ = ("MolterContext",)


@attrs.define(slots=True)
class MolterContext:
    """
    A special 'Context' object for `molter`'s commands.
    This does not actually inherit from `interactions._Context`.
    """

    client: "MolterInjectedClient" = attrs.field()
    """The bot instance."""
    message: interactions.Message = attrs.field()
    """The message this represents."""
    user: interactions.User = attrs.field()
    """The user who sent the message."""
    member: typing.Optional[interactions.Member] = attrs.field()
    """The guild member who sent the message, if applicable."""

    channel: typing.Optional[interactions.Channel] = attrs.field()
    """The channel this message was sent through, if applicable.
    Will be `None` if `Molter.fetch_data_for_context` is False
    unless `MolterContext.get_channel` is used."""
    guild: typing.Optional[interactions.Guild] = attrs.field()
    """The guild this message was sent through, if applicable.
    Will be `None` if `Molter.fetch_data_for_context` is False
    unless `MolterContext.get_guild` is used."""

    invoked_name: str = attrs.field(default=None)
    """The name/alias used to invoke the command."""
    content_parameters: str = attrs.field(default=None)
    """The message content without the prefix or command."""
    command: "MolterCommand" = attrs.field(default=None)
    """The command invoked."""
    args: typing.List[str] = attrs.field(factory=list)
    """The arguments of the command (as a list of strings)."""
    prefix: str = attrs.field(default=None)
    """The prefix used for this command."""

    def __attrs_post_init__(self) -> None:
        for inter_object in (
            self.message,
            self.member,
            self.channel,
            self.guild,
        ):
            if not inter_object or "_client" not in inter_object.__slots__:
                continue
            inter_object._client = self._http

    @property
    def author(self):
        """
        Either the member or user who sent the message. Prefers member,
        but defaults to user if the member does not exist.
        This is useful for getting a Discord user, regardless of if the
        message was from a guild or not.
        """
        return self.member or self.user

    @property
    def bot(self) -> interactions.Client:
        """An alias to `MolterContext.client`."""
        return self.client

    @property
    def channel_id(self) -> interactions.Snowflake:
        """Returns the channel ID where the message was sent."""
        return self.message.channel_id  # type: ignore

    @property
    def guild_id(self) -> typing.Optional[interactions.Snowflake]:
        """Returns the guild ID where the message was sent, if applicable."""
        return self.message.guild_id

    @property
    def _http(self) -> interactions.HTTPClient:
        """Returns the HTTP client the client has."""
        return self.client._http

    async def get_channel(self):
        """Gets the channel where the message was sent."""
        if self.channel:
            return self.channel

        self.channel = await self.message.get_channel()
        return self.channel

    async def get_guild(self):
        """Gets the guild where the message was sent, if applicable."""
        if not self.guild_id:
            return None

        self.guild = await self.message.get_guild()
        return self.guild

    async def _get_channel_for_send(self) -> interactions.Channel:
        """
        Gets the channel to send a message for.
        Unlike `get_channel`, we don't exactly need a channel with
        fully correct attributes, so a cached result works well enough.
        """

        if self.channel:
            return self.channel

        if channel := self._http.cache.channels.get(str(self.channel_id)):
            return channel.value

        return await self.get_channel()

    async def send(
        self,
        content: typing.Optional[str] = interactions.MISSING,  # type: ignore
        *,
        tts: typing.Optional[bool] = interactions.MISSING,  # type: ignore
        files: typing.Optional[
            typing.Union[interactions.File, typing.List[interactions.File]]
        ] = interactions.MISSING,  # type: ignore
        embeds: typing.Optional[
            typing.Union["interactions.Embed", typing.List["interactions.Embed"]]
        ] = interactions.MISSING,  # type: ignore
        allowed_mentions: typing.Optional[
            "interactions.MessageInteraction"
        ] = interactions.MISSING,  # type: ignore
        components: typing.Optional[
            typing.Union[
                "interactions.ActionRow",
                "interactions.Button",
                "interactions.SelectMenu",
                typing.List["interactions.ActionRow"],
                typing.List["interactions.Button"],
                typing.List["interactions.SelectMenu"],
            ]
        ] = interactions.MISSING,  # type: ignore
        **kwargs,
    ) -> "interactions.Message":  # type: ignore
        """
        Sends a message in the channel where the message came from.

        :param content?: The contents of the message as a string or \
            string-converted value.
        :type content: Optional[str]
        :param tts?: Whether the message utilizes the text-to-speech Discord \
            programme or not.
        :type tts: Optional[bool]
        :param files?: A file or list of files to be attached to the message.
        :type files: Optional[Union[File, List[File]]]
        :param embeds?: An embed, or list of embeds for the message.
        :type embeds: Optional[Union[Embed, List[Embed]]]
        :param allowed_mentions?: The message interactions/mention limits \
            that the message can refer to.
        :type allowed_mentions: Optional[MessageInteraction]
        :param components?: A component, or list of components for the message.
        :type components: Optional[Union[ActionRow, Button, SelectMenu, \
            List[Actionrow], List[Button], List[SelectMenu]]]
        :return: The sent message as an object.
        :rtype: Message
        """

        channel = await self._get_channel_for_send()
        return await channel.send(
            content,
            tts=tts,
            files=files,
            embeds=embeds,
            allowed_mentions=allowed_mentions,
            components=components,
            **kwargs,
        )

    async def reply(
        self,
        content: typing.Optional[str] = interactions.MISSING,  # type: ignore
        *,
        tts: typing.Optional[bool] = interactions.MISSING,  # type: ignore
        files: typing.Optional[
            typing.Union[interactions.File, typing.List[interactions.File]]
        ] = interactions.MISSING,  # type: ignore
        embeds: typing.Optional[
            typing.Union["interactions.Embed", typing.List["interactions.Embed"]]
        ] = interactions.MISSING,  # type: ignore
        allowed_mentions: typing.Optional[
            "interactions.MessageInteraction"
        ] = interactions.MISSING,  # type: ignore
        components: typing.Optional[
            typing.Union[
                "interactions.ActionRow",
                "interactions.Button",
                "interactions.SelectMenu",
                typing.List["interactions.ActionRow"],
                typing.List["interactions.Button"],
                typing.List["interactions.SelectMenu"],
            ]
        ] = interactions.MISSING,  # type: ignore
        **kwargs,
    ) -> "interactions.Message":  # type: ignore
        """
        Sends a new message replying to the old.

        :param content?: The contents of the message as a string or \
            string-converted value.
        :type content: Optional[str]
        :param tts?: Whether the message utilizes the text-to-speech Discord \
            programme or not.
        :type tts: Optional[bool]
        :param files?: A file or list of files to be attached to the message.
        :type files: Optional[Union[File, List[File]]]
        :param embeds?: An embed, or list of embeds for the message.
        :type embeds: Optional[Union[Embed, List[Embed]]]
        :param allowed_mentions?: The message interactions/mention limits \
            that the message can refer to.
        :type allowed_mentions: Optional[MessageInteraction]
        :param components?: A component, or list of components for the message.
        :type components: Optional[Union[ActionRow, Button, SelectMenu, \
            List[Actionrow], List[Button], List[SelectMenu]]]
        :return: The sent message as an object.
        :rtype: Message
        """

        return await self.message.reply(
            content,
            tts=tts,
            files=files,
            embeds=embeds,
            allowed_mentions=allowed_mentions,
            components=components,
            **kwargs,
        )
