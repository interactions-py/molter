import typing

import attrs

import interactions
import interactions.api.error as inter_error
from .cache import CacheHandler

if typing.TYPE_CHECKING:
    from .command import MolterCommand

__all__ = ("MolterContext",)


@attrs.define(slots=True)
class MolterContext:
    """
    A special 'Context' object for `molter`'s commands.
    This does not actually inherit from `interactions._Context`.
    """

    client: interactions.Client = attrs.field()
    """The bot instance."""
    message: interactions.Message = attrs.field()
    """The message this represents."""
    user: interactions.User = attrs.field()
    """The user who sent the message."""
    member: typing.Optional[interactions.Member] = attrs.field()
    """The guild member who sent the message, if applicable."""
    channel: typing.Optional[interactions.Channel] = attrs.field()
    """The channel this message was sent through, if applicable.
    Will be `None` if `Molter.fetch_data_for_context` is False."""
    guild: typing.Optional[interactions.Guild] = attrs.field()
    """The guild this message was sent through, if applicable.
    Will be `None` if `Molter.fetch_data_for_context` is False."""

    invoked_name: str = attrs.field(default=None)
    """The name/alias used to invoke the command."""
    command: "MolterCommand" = attrs.field(default=None)
    """The command invoked."""
    args: list[str] = attrs.field(factory=list)
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
            inter_object._client = self.client._http

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
    def content_parameters(self) -> str:
        """The message content without the prefix or command."""
        return self.message.content.removeprefix(
            f"{self.prefix}{self.invoked_name}"
        ).strip()

    async def get_channel(self) -> interactions.Channel:
        """Gets the channel where the message was sent."""
        if self.channel:
            return self.channel

        self.channel = await CacheHandler.fetch_channel(self.channel_id)
        return self.channel  # type: ignore

    async def get_guild(self):
        """Gets the guild where the message was sent, if applicable."""
        if self.guild:
            return self.guild

        self.guild = await CacheHandler.fetch_guild(self.guild_id)
        return self.guild

    async def send(
        self,
        content: typing.Optional[str] = interactions.MISSING,  # type: ignore
        *,
        tts: typing.Optional[bool] = interactions.MISSING,  # type: ignore
        embeds: typing.Optional[
            typing.Union["interactions.Embed", list["interactions.Embed"]]
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

        channel = await self.get_channel()
        await channel.send(
            content,
            tts=tts,
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
        embeds: typing.Optional[
            typing.Union["interactions.Embed", list["interactions.Embed"]]
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

        await self.message.reply(
            content,
            tts=tts,
            embeds=embeds,
            allowed_mentions=allowed_mentions,
            components=components,
            **kwargs,
        )
