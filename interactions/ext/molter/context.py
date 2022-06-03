import typing

import attrs

import interactions

if typing.TYPE_CHECKING:
    from .command import MolterCommand
    from .base import MolterInjectedClient

__all__ = (
    "MolterContext",
    "HybridContext",
)


ALL_PERMISSIONS = interactions.Permissions(0)

for perm in interactions.Permissions:
    ALL_PERMISSIONS |= perm


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
    user: interactions.User = attrs.field()
    """The user who sent the message."""
    member: typing.Optional[interactions.Member] = attrs.field(default=None)
    """The guild member who sent the message, if applicable."""

    channel: typing.Optional[interactions.Channel] = attrs.field(default=None)
    """The channel this message was sent through, if applicable.
    Will be `None` if `Molter.fetch_data_for_context` is False
    unless `MolterContext.get_channel` is used."""
    guild: typing.Optional[interactions.Guild] = attrs.field(default=None)
    """The guild this message was sent through, if applicable.
    Will be `None` if `Molter.fetch_data_for_context` is False
    unless `MolterContext.get_guild` is used."""

    invoked_name: str = attrs.field(init=False, default=None)
    """The name/alias used to invoke the command."""
    content_parameters: str = attrs.field(init=False, default=None)
    """The message content without the prefix or command."""
    command: "MolterCommand" = attrs.field(init=False, default=None)
    """The command invoked."""
    args: typing.List[str] = attrs.field(init=False, factory=list)
    """The arguments of the command (as a list of strings)."""
    prefix: str = attrs.field(default=None)
    """The prefix used for this command."""

    extras: typing.Dict[typing.Any, typing.Any] = attrs.field(
        init=False, factory=dict, repr=False
    )
    """Extras used for this context. These can contain your own custom data."""

    _guild_permissions: typing.Optional[interactions.Permissions] = attrs.field(
        init=False, default=None
    )
    _channel_permissions: typing.Optional[interactions.Permissions] = attrs.field(
        init=False, default=None
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
    def author(self) -> typing.Union[interactions.Member, interactions.User]:
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

    async def get_channel(self) -> interactions.Channel:
        """Gets the channel where the message was sent."""
        if self.channel:
            return self.channel

        self.channel = await self.message.get_channel()
        return self.channel

    async def get_guild(self) -> typing.Optional[interactions.Guild]:
        """Gets the guild where the message was sent, if applicable."""
        if self.guild:
            return self.guild

        if not self.guild_id:
            return None

        self.guild = await self.message.get_guild()
        return self.guild

    async def compute_guild_permissions(self) -> interactions.Permissions:
        """
        Computes the guild (role-only) permissions for the member that sent the message.
        This factors in ownership and the roles of the member.

        The result may be expensive to compute, so it is cached after its first use.
        The context must have a guild ID and member set.

        This uses the pseudocode featured in Discord's own documentation about
        permission overwrites as a base.

        Returns:
            `interactions.Permissions`: The guild permissions for the member
            that sent the message.
        """
        if self._guild_permissions:
            return self._guild_permissions

        if not self.member:
            raise ValueError("This context doesn't have a member!")

        guild = await self.get_guild()

        if not guild:
            raise ValueError("This context doesn't have a guild!")

        if int(self.user.id) == guild.owner_id:
            self._guild_permissions = ALL_PERMISSIONS
            return ALL_PERMISSIONS

        roles = await guild.get_all_roles()

        role_everyone = next(r for r in roles if r.id == guild.id)
        permissions = interactions.Permissions(int(role_everyone.permissions))

        if self.member.roles:
            member_roles = [r for r in roles if int(r.id) in self.member.roles]
        else:
            member_roles = []

        for role in member_roles:
            permissions |= interactions.Permissions(int(role.permissions))

        if (
            permissions & interactions.Permissions.ADMINISTRATOR
            == interactions.Permissions.ADMINISTRATOR
        ):
            self._guild_permissions = ALL_PERMISSIONS
            return ALL_PERMISSIONS

        self._guild_permissions = permissions
        return permissions

    async def _compute_overwrites(self, base_permissions: interactions.Permissions):
        """Calculates and adds in overwrites based on the guild permissions."""
        if self._channel_permissions:
            return self._channel_permissions
        if (
            base_permissions & interactions.Permissions.ADMINISTRATOR
            == interactions.Permissions.ADMINISTRATOR
        ):
            self._channel_permissions = ALL_PERMISSIONS
            return ALL_PERMISSIONS

        if not self.member:
            raise ValueError("This context doesn't have a member!")

        if not self.guild_id:
            raise ValueError("This context doesn't have a guild!")

        channel = await self.get_channel()

        permissions = base_permissions
        overwrites = channel.permission_overwrites

        if overwrite_everyone := next(
            (o for o in overwrites if o.id == int(self.guild_id)), None
        ):
            permissions &= ~interactions.Permissions(int(overwrite_everyone.deny))
            permissions |= interactions.Permissions(int(overwrite_everyone.allow))

        allow = interactions.Permissions(0)
        deny = interactions.Permissions(0)

        for role_id in self.member.roles:
            if overwrite_role := next(
                (o for o in overwrites if o.id == str(role_id)), None
            ):
                allow |= interactions.Permissions(int(overwrite_role.allow))
                deny |= interactions.Permissions(int(overwrite_role.deny))

        permissions &= ~deny
        permissions |= allow

        if overwrite_member := next(
            (o for o in overwrites if o.id == str(self.member.id)), None
        ):
            permissions &= ~interactions.Permissions(int(overwrite_member.deny))
            permissions |= interactions.Permissions(int(overwrite_member.allow))

        self._channel_permissions = permissions
        return permissions

    async def compute_permissions(self) -> interactions.Permissions:
        """
        Computes the permissions for the member that sent the message.
        This factors in ownership, roles, and channel overwrites.

        The result may be expensive to compute, so it is cached after its first use.
        Unlike compute_guild_permissions, this works for DM messages.

        This uses the pseudocode featured in Discord's own documentation about
        permission overwrites as a base.

        Returns:
            `interactions.Permissions`: The permissions for the member
            that sent the message.
        """

        if self._channel_permissions:
            return self._channel_permissions

        if not self.guild_id:
            # basic text permissions, no tts, yes view channel
            return interactions.Permissions(0b1111100110001000000)

        base_permissions = await self.compute_guild_permissions()
        return await self._compute_overwrites(base_permissions)

    def _get_channel_for_send(self) -> interactions.Channel:
        """
        Gets the channel to send a message for.
        Unlike `get_channel`, we don't exactly need a channel with
        fully correct attributes, so we can use a dummy channel here.
        """

        # this is a dummy channel - we don't really care about the type or much of anything
        # so we've included the basics like the id and the client and that's it
        # really, if i could remove the type, i would
        return self.channel or interactions.Channel(
            id=self.channel_id, type=0, _client=self._http
        )

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

        channel = self._get_channel_for_send()
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
            components=components,
            **kwargs,
        )


@attrs.define()
class HybridContext(MolterContext):
    """
    A special subclass of `MolterContext` for hybrid commands.
    This tries to handle the differences between slash and prefixed commands seemlessly.
    """

    client: "typing.Optional[MolterInjectedClient]" = attrs.field(default=None)
    """The bot instance. This will not appear for slash command versions."""
    message: typing.Optional[interactions.Message] = attrs.field(default=None)
    """The message this represents."""

    interaction: typing.Optional[interactions.CommandContext] = attrs.field(
        default=None
    )
    """The interaction context, if this is for the slash command version."""

    def __attrs_post_init__(self) -> None:
        if self.interaction and self.interaction.member:
            self._channel_permissions = self.interaction.member.permissions

        return super().__attrs_post_init__()

    @property
    def bot(self) -> "typing.Optional[MolterInjectedClient]":
        """An alias to `MolterContext.client`."""
        return self.client

    @property
    def channel_id(self) -> interactions.Snowflake:
        """Returns the channel ID where the message was sent."""
        return self.interaction.channel_id if self.interaction else self.message.channel_id  # type: ignore

    @property
    def guild_id(self) -> typing.Optional[interactions.Snowflake]:
        """Returns the guild ID where the message was sent, if applicable."""
        return self.interaction.guild_id if self.interaction else self.message.guild_id  # type: ignore

    @property
    def _http(self) -> interactions.HTTPClient:
        """Returns the HTTP client the client has."""
        return self.interaction.client if self.interaction else self.client._http

    async def get_channel(self) -> interactions.Channel:
        """Gets the channel where the message was sent."""
        if self.channel:
            return self.channel

        if self.interaction:
            self.channel = await self.interaction.get_channel()
        else:
            self.channel = await self.message.get_channel()  # type: ignore
        return self.channel

    async def get_guild(self) -> typing.Optional[interactions.Guild]:
        """Gets the guild where the message was sent, if applicable."""
        if self.guild:
            return self.guild

        if not self.guild_id:
            return None

        if self.interaction:
            self.guild = await self.interaction.get_guild()
        else:
            self.guild = await self.message.get_guild()  # type: ignore
        return self.guild

    async def defer(self, ephemeral: bool = False):
        """
        Either defers the interaction (if present) or simply triggers a
        typing indicator in the channel for 10 seconds.

        Args:
            ephemeral (`bool`, optional): Whether the response is hidden or not.
            This property is ignored for prefixed commands.
        """
        if self.interaction:
            return await self.interaction.defer(ephemeral)

        await self._http.trigger_typing(int(self.channel_id))

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
        ephemeral: bool = False,
        **kwargs,
    ) -> "interactions.Message":  # type: ignore
        """
        Either responds to an interaction (if present) or sends a message in the
        channel where the message came from.

        Args:
            content (`str`, optional): The contents of the message as a string
            or string-converted value.

            tts (`bool`, optional): Whether the message utilizes the text-to-speech
            Discord programme or not.

            files (`interactions.File | list[interactions.File]`, optional):
            A file or list of files to be attached to the message.
            This property is ignored for interactions.

            embeds (`interactions.Embed | list[interactions.Embed]`, optional):
            An embed, or list of embeds for the message.

            allowed_mentions (`interactions.MessageInteraction`, optional):
            The message interactions/mention limits that the message can refer to.

            components (`interactions.ActionRow | interactions.Button |
            interactions.SelectMenu | list[interactions.ActionRow] |
            list[interactions.Button] | list[interactions.SelectMenu]`, optional):
            A component, or list of components for the message.

            ephemeral (`bool`, optional): Whether the response is hidden or not.
            This property is ignored for prefixed commands.

        Returns:
            `interactions.Message`: The sent message as an object.
        """

        if self.interaction:
            return await self.interaction.send(
                content,
                tts=tts,
                embeds=embeds,
                allowed_mentions=allowed_mentions,
                components=components,
                ephemeral=ephemeral,
                **kwargs,
            )

        channel = self._get_channel_for_send()
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
        ephemeral: bool = False,
        **kwargs,
    ) -> "interactions.Message":  # type: ignore
        """
        Either responds to an interaction (if present) or sends a new message replying to the old.

        Args:
            content (`str`, optional): The contents of the message as a string
            or string-converted value.

            tts (`bool`, optional): Whether the message utilizes the text-to-speech
            Discord programme or not.

            files (`interactions.File | list[interactions.File]`, optional):
            A file or list of files to be attached to the message.
            This property is ignored for interactions.

            embeds (`interactions.Embed | list[interactions.Embed]`, optional):
            An embed, or list of embeds for the message.

            allowed_mentions (`interactions.MessageInteraction`, optional):
            The message interactions/mention limits that the message can refer to.

            components (`interactions.ActionRow | interactions.Button |
            interactions.SelectMenu | list[interactions.ActionRow] |
            list[interactions.Button] | list[interactions.SelectMenu]`, optional):
            A component, or list of components for the message.

            ephemeral (`bool`, optional): Whether the response is hidden or not.
            This property is ignored for prefixed commands.

        Returns:
            `interactions.Message`: The sent message as an object.
        """

        if self.interaction:
            return await self.interaction.send(
                content,
                tts=tts,
                embeds=embeds,
                allowed_mentions=allowed_mentions,
                components=components,
                ephemeral=ephemeral,
                **kwargs,
            )

        return await self.message.reply(
            content,
            tts=tts,
            files=files,
            embeds=embeds,
            allowed_mentions=allowed_mentions,
            components=components,
            **kwargs,
        )
