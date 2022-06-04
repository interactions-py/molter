import interactions
from interactions.ext import molter

# This file assumes you've already looked at "extension.py".
# It also assumes you're familiar with interactions.py's slash commands.

# This is just a scope - it's set to 0 here, but you can set it to a
# testing guild to test this part out.
GUILD_ID = 0


class HybridExtension(molter.MolterExtension):
    def __init__(self, bot: interactions.Client) -> None:
        self.bot = bot

    # What are hybrid commands? They're both a slash comamnd and a molter
    # prefixed command, of course! They're a neat way of having both if you
    # want to do so for whatever reason (easing people into slash commands
    # being the biggest one).

    # As of right now, molter only supports making hybrid commands from slash
    # commands. Hybrid commands from prefixed commands may be added in the future,
    # but are much more complex to do behind-the-scenes, so I've decided not to
    # do them for now.

    # Hybrid slash commands are made very similar to how you make slash commands -
    # in fact, we're using an example straight from interaction.py's
    # quickstart guide, as you can see here:
    # https://discord-interactions.readthedocs.io/en/latest/quickstart.html#nested-commands-subcommands

    # I used that specific example here because it shows a couple of things
    # about hybrid commands:

    # 1. They use a different decorator than interaction.py's decorators, but
    # that's expected. You can use the decorator below for extensions,
    # and Molter.hybrid_slash in your main file. "Molter" is what you get from
    # molter.setup, by the way.
    #
    # 2. They require molter to be initializied, and for extensions, require using
    # MolterExtension. There isn't much I can do about this.
    #
    # 3. They support most of the options slash commands usually support. The only
    # one missing is the "type" parameter as, well, you're making a slash command,
    # there isn't much of a point to specify it.
    #
    # 4. They support options and subcommands. Not shown here, but also equally
    # supported, is subcommand groups.
    #
    # 5. A special context, HybridContext, is used instead of either CommandContext
    # or MolterContext. HybridContext is a subclass of MolterContext with a number
    # of utility methods to seemlessly handle both slash commands and prefixed commands.
    # However, for some special slash command actions, like sending a model, there is
    # HybridContext.command_context, which returns the inner CommandContext if the command
    # is being run as a slash command.

    # There are a number of things not quite shown by this example alone, so let's
    # go over some other points:

    # 1. scope, default_member_permissions, and dm_permission are all enforced by
    # prefixed commands via checks, throwing a CheckFailure if they don't match.
    # Unlike slash commands, prefixed commands FORCE default_member_permissions,
    # unable to be changed due to the fact that molter has no way of finding out what
    # the server changed the permissions to.
    #
    # 2. Autocomplete is... really a mixed bag. molter has no true way of supporting
    # them - due to how interactions.py handles autocomplete, we have no real way of
    # getting the function that handles it. Also, even if we did, prefixed commands
    # don't really have a way of suggesting inputs as the user types. Instead,
    # molter just passes the raw input all the way through, so you'll have to make sure
    # to deal with it. As a heads up, molter will warn about this if it detects an
    # autocomplete option.
    #
    # 3. In prefixed command world for subcommands and groups, the base command
    # IS usable, but will error out with a BadArgument when run.
    #
    # 4. Prefixed commands have their help description set to the description of
    # the base command. Options are not passed through to the description.
    #
    # 5. For integers and numbers (floats), prefixed commands have a 64-bit size limit,
    # unlike Discord's more restrictive -2^53 to 2^53 range.
    #
    # 6. All current option types are supported. However, due to how they are handled,
    # some options, like MENTIONABLE, may make the prefixed command take more time to
    # trigger compared to the slash command version. This is a limitation of interactions.py
    # and its currently unusable cache, meaning we have to fetch everything from Discord
    # (which, yeah, takes time).
    #
    # 7. Yes, basic commands with no groups work.
    #
    # 8. No, molter's checks do not work here.

    # The below is formatted with black, unlike the original example, by the way.
    @molter.extension_hybrid_slash(
        name="base_command",
        description="This description isn't seen in UI (yet?)",
        scope=GUILD_ID,
        options=[
            interactions.Option(
                name="command_name",
                description="A descriptive description",
                type=interactions.OptionType.SUB_COMMAND,
                options=[
                    interactions.Option(
                        name="option",
                        description="A descriptive description",
                        type=interactions.OptionType.INTEGER,
                        required=False,
                    ),
                ],
            ),
            interactions.Option(
                name="second_command",
                description="A descriptive description",
                type=interactions.OptionType.SUB_COMMAND,
                options=[
                    interactions.Option(
                        name="second_option",
                        description="A descriptive description",
                        type=interactions.OptionType.STRING,
                        required=True,
                    ),
                ],
            ),
        ],
    )
    async def cmd(
        self,
        ctx: molter.HybridContext,
        sub_command: str,
        second_option: str = "",
        option: int = None,
    ):
        if sub_command == "command_name":
            await ctx.reply(
                f"You selected the command_name sub command and put in {option}"
            )
        elif sub_command == "second_command":
            await ctx.reply(
                "You selected the second_command sub command and put in"
                f" {second_option}"
            )


def setup(bot: interactions.Client):
    HybridExtension(bot)
