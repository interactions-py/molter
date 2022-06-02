import typing
import interactions

def extension_hybrid_slash(
    *,
    name: typing.Optional[str] = None,
    description: typing.Optional[str] = None,
    scope: typing.Optional[
        typing.Union[
            int, interactions.Guild, typing.List[int], typing.List[interactions.Guild]
        ]
    ] = None,
    options: typing.Optional[
        typing.Union[
            typing.Dict[str, typing.Any],
            typing.List[typing.Dict[str, typing.Any]],
            interactions.Option,
            typing.List[interactions.Option],
        ]
    ] = None,
    name_localizations: typing.Optional[
        typing.Dict[typing.Union[str, interactions.Locale], str]
    ] = None,
    description_localizations: typing.Optional[
        typing.Dict[typing.Union[str, interactions.Locale], str]
    ] = None,
    default_member_permissions: typing.Optional[
        typing.Union[int, interactions.Permissions]
    ] = None,
    dm_permission: typing.Optional[bool] = None
): ...
