from typing import Union

import interactions
from interactions.ext import molter

client = interactions.Client(
    token="YOUR TOKEN HERE",
    intents=interactions.Intents.DEFAULT | interactions.Intents.GUILD_MESSAGE_CONTENT,
)

# As you can see, this is how the generate_prefixes argument looks like.
# You could easily use this to fetch data from a database to have dynamic prefixes
# or simply to have guild-specific prefixes.
async def generate_prefixes(bot: interactions.Client, msg: interactions.Message):
    # Fetching from the database could look something like:
    # prefixes = await bot.db.fetch(
    #   f"SELECT prefixes FROM guild_config WHERE guild_id = {msg.guild_id}"
    # )

    # But to make this example work, we'll just do:
    prefixes = ("!",)
    return await molter.when_mentioned_or(*prefixes)(bot, msg)
    # when_mentioned_or is a utility function that allows you to specify
    # prefixes as well as having the bot respond to it being mentioned.
    # Using it in your own generate_prefixes is a bit weird and looks
    # like this, though using it in the generate_prefixes argument
    # is as simple as:
    # generate_prefixes=when_mentioned_or("prefix", "prefix2")
    # when_mentioned is also a function provided, if you want to use it.

    # Note that if you just want to have a static prefix (or prefixes),
    # use the default_prefix argument for Molter instead.


# You can see here we pass our generate_prefixes here.
# generate_prefixes automatically supercedes default_prefix if both are
# provided.

# As promised, fetch_data_for_context is a rather weird argument:
# By default, MolterContext has its guild and channel arguments set to None
# and you would have to get them via get_channel and get_guild.
# This is done for speed purposes - to provide those two arguments,
# we need to fetch the channel and guild from Discord's API due to how
# interactions.py works, taking up time and generally being somewhat slow.
# However, if you are okay with that slowdown and want those two anyways without
# fetching it yourself, you can pass fetch_data_for_context=True to do so.
molt = molter.setup(
    client, generate_prefixes=generate_prefixes, fetch_data_for_context=True
)


# Let's be a bit more advanced, shall we?
# As you can see, this command will not be run by doing !a_name or the like -
# the user will need to do !test.
# Furthermore, we used ignore_extra so that if a user provided an argument beyond
# a member/user, the command will error out.
# (Using "!test @Astrea e" would error out, for example.)

# Speaking of that argument, it's a weird one, isn't it?
# Unions (or | if you're using Python 3.10) are a way of specifying a variable
# possibly have two types, depending on the input passed.
# Unions in molter work a similar way to it, with molter running through each type
# in the Union to see if the input matches any of the types/converters.
# In this case, we're seeing if the input provided is a member of whatever guild we're
# running this command on first, and if we don't find them, see if they're a user at all.

# BTW, interactions.py types all have a converter behind the scenes that converts inputs
# into them.
# Take a look at molter's converters.py - they have all of the default ones.
# Most inter.py type converters are smart and take multiple inputs, like names, mentions,
# IDs, etc, and converts them into objects.
# Unlike discord.py or dis-snek though, some objects can only take IDs due to technical
# reasons.
# Converters will be talked more in-depth in the extension.
@molt.message_command(name="test", ignore_extra=False)
async def a_name(
    ctx: molter.MolterContext,
    member_or_user: Union[interactions.Member, interactions.User],
):
    await ctx.reply(member_or_user.mention)


# Loading the other file to this example, don't mind me.
client.load("extension")
client.start()
