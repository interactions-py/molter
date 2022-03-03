import typing

import attrs

import interactions

if typing.TYPE_CHECKING:
    from .command import MolterCommand


@attrs.define(slots=True)
class MolterContext:
    """
    A special 'Context' object for `molter`'s commands.
    This does not actually inherit from `interactions._Context`.

    Parameters:
        client (`interactions.Client`): The bot instance.
        message (`interactions.Message`): The message this represents.
        user (`interactions.Message`): The user who sent the message.
        member (`interactions.Message`, optional): The guild member of \
            the person who sent the message, if applicable.
        channel (`interactions.Message`): The channel this message \
            was sent through.
        guild (`interactions.Message`, optional): The channel this message \
            was sent through, if applicable.
    """

    client: interactions.Client = attrs.field()
    message: interactions.Message = attrs.field()
    user: interactions.User = attrs.field()
    member: typing.Optional[interactions.Member] = attrs.field()
    channel: interactions.Channel = attrs.field()
    guild: typing.Optional[interactions.Guild] = attrs.field()

    invoked_name: str = attrs.field(default=None)
    command: "MolterCommand" = attrs.field(default=None)
    args: list[str] = attrs.field(factory=list)
    prefix: str = attrs.field(default=None)

    def __attrs_post_init__(self) -> None:
        for inter_object in (
            self.message,
            self.member,
            self.channel,
            self.guild,
        ):
            if not inter_object or not "_client" in inter_object.__slots__:
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
        return self.client

    @property
    def content_parameters(self) -> str:
        return self.message.content.removeprefix(
            f"{self.prefix}{self.invoked_name}"
        ).strip()

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

        await self.channel.send(
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
