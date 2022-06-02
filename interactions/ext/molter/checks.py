import typing

import interactions
from .command import MCT
from .command import MolterCommand
from .errors import CheckFailure

if typing.TYPE_CHECKING:
    from .context import MolterContext


__all__ = ("check", "has_permissions", "has_guild_permissions")


def check(
    check: typing.Callable[
        ["MolterContext"], typing.Coroutine[typing.Any, typing.Any, bool]
    ]
) -> typing.Callable[..., MCT]:
    """
    Add a check to a command.

    Args:
        check: A coroutine as a check for this command.
    """

    def wrapper(coro: MCT) -> MCT:
        if isinstance(coro, MolterCommand):
            coro.checks.append(check)
            return coro
        if not hasattr(coro, "checks"):
            coro.__checks__ = []  # type: ignore
        coro.__checks__.append(check)  # type: ignore
        return coro

    return wrapper


def has_permissions(
    *permissions: interactions.Permissions,
) -> typing.Callable[..., MCT]:
    """
    A check to see if the member has permissions specified for the specific context.
    Considers guild ownership, roles, and channel overwrites.
    Will fail in DMs.

    Args:
        permissions (`interactions.Permissions`): A list of permissions to check.
    """

    combined_permissions = interactions.Permissions(0)
    for perm in permissions:
        combined_permissions |= perm

    async def _permission_check(ctx: "MolterContext"):
        member_permissions = await ctx.compute_permissions()
        result = combined_permissions in member_permissions

        if not result:
            raise CheckFailure(
                ctx, "You do not have the proper permissions to use this command."
            )
        return result

    return check(_permission_check)  # type: ignore


def has_guild_permissions(
    *permissions: interactions.Permissions,
) -> typing.Callable[..., MCT]:
    """
    A check to see if the member has permissions specified for the guild.
    Considers guild ownership and roles.
    Will fail in DMs.

    Args:
        permissions (`interactions.Permissions`): A list of permissions to check.
    """

    combined_permissions = interactions.Permissions(0)
    for perm in permissions:
        combined_permissions |= perm

    async def _permission_check(ctx: "MolterContext"):
        guild_permissions = await ctx.compute_guild_permissions()
        result = combined_permissions in guild_permissions

        if not result:
            raise CheckFailure(
                ctx, "You do not have the proper permissions to use this command."
            )
        return result

    return check(_permission_check)  # type: ignore
