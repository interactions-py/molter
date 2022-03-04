import typing
from collections import defaultdict

import interactions
import interactions.api.error as inter_error
from . import utils

__all__ = ("CacheHandler",)

T = typing.TypeVar("T")


class _CacheHandler(utils.Sentinel):
    """
    A handler for interacting with `interactions`'s cache in a sane way.
    Born out of frustration with having to poke around with internals to use it.
    """

    _http: interactions.HTTPClient

    # the member cache in inter.py is broken as it does not seperate members by guild
    # this will make it have invalid data if a member is gotten from multiple guilds
    _member_cache: defaultdict[str, dict[str, interactions.Member]]

    def _init_cache(self, http: interactions.HTTPClient):
        """
        Adds the required fields into the handler, allowing it to be used.
        If you are using molter, this is done upon initializing the `Molter` class.

        Args:
            http (interactions.HTTPClient): _description_
        """
        self._member_cache = defaultdict(dict)
        self._http = http

    def _inter_cache_get(self, snowflake_id: str, access: str):
        if item_object := getattr(self._http.cache, f"{access}s").get(snowflake_id):
            object = item_object
            if "_client" in object.__slots__:
                object._client = self._http
            return object
        return None

    async def _fetch(
        self, snowflake_id: str, access: str, class_var: type[T]
    ) -> typing.Optional[T]:
        if object := self._inter_cache_get(snowflake_id, access):
            return object

        try:
            data = await getattr(self._http, f"get_{access}")(int(snowflake_id))
            return class_var(**data, _client=self._http)
        except inter_error.HTTPException:
            return None

    async def fetch_guild(self, guild_id: utils.OptionalSnowflakeType):
        if not guild_id:
            return None
        return await self._fetch(str(guild_id), "guild", interactions.Guild)

    async def fetch_user(self, user_id: utils.OptionalSnowflakeType):
        if not user_id:
            return None
        return await self._fetch(str(user_id), "user", interactions.User)

    async def fetch_channel(self, channel_id: utils.OptionalSnowflakeType):
        if not channel_id:
            return None
        return await self._fetch(str(channel_id), "channel", interactions.Channel)

    async def fetch_member(
        self,
        guild_id: utils.OptionalSnowflakeType,
        member_id: utils.OptionalSnowflakeType,
    ):
        if not guild_id or not member_id:
            return None

        if member := self._member_cache[str(guild_id)].get(str(member_id)):
            return member

        try:
            data = await self._http.get_member(int(guild_id), int(member_id))
            member = interactions.Member(**data, _client=self._http)  # type: ignore
            self._member_cache[str(guild_id)][str(member_id)] = member
            return member
        except inter_error.HTTPException:
            return None

    async def fetch_role(
        self,
        guild_id: utils.OptionalSnowflakeType,
        role_id: utils.OptionalSnowflakeType,
    ) -> typing.Optional[interactions.Role]:
        if not guild_id or not role_id:
            return None

        if role := self._inter_cache_get(str(role_id), "role"):
            return role

        roles = await self._http.get_all_roles(int(guild_id))
        return next(
            (
                interactions.Role(**i, _client=self._http)
                for i in roles
                if int(i["id"]) == int(role_id)
            ),
            None,
        )


CacheHandler = _CacheHandler()
"""
A handler for interacting with `interactions`'s cache in a sane way.
Since this is a `Sentinel`, this can be used by simply importing it.

If you wish to run with without loading `Molter`, please use
`CacheHandler._init_cache(http)` beforehand.
"""
