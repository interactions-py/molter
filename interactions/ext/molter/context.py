import typing as _typing

import attrs

import interactions
from . import utils

if _typing.TYPE_CHECKING:
    from .command import MolterCommand
    from .base import MolterInjectedClient

__all__ = ("MolterContext",)


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

        if not self.guild:
            raise ValueError("This context doesn't have a guild!")

        if int(self.user.id) == self.guild.owner_id:
            self._guild_permissions = ALL_PERMISSIONS
            return ALL_PERMISSIONS

        roles = (
            await self.guild.get_all_roles()
        )  # sadly, has to be done to guarantee accurate info

        role_everyone = next(r for r in roles if r.id == self.guild_id)
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

        permissions = base_permissions

        if overwrites := self.channel.permission_overwrites:
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
            id=self.channel_id, type=0, _client=self._http  # type: ignore
        )

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

        channel = self._get_channel_for_send()
        return await channel.send(
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
