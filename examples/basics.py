import interactions
from interactions.ext import molter


# This first part should look rather normal.
# It's initializing the Client, providing our token and all.
# Enabling the guild message intent is highly recommended, as otherwise you will
# be limited to messages that ping the bot for message/prefix/molter commands.
bot = interactions.Client(
    token="YOUR TOKEN HERE",
    intents=interactions.Intents.DEFAULT | interactions.Intents.GUILD_MESSAGE_CONTENT,
)

# Here's where things get interesting, huh?
# We actually do not want to load molter as an extension - it'll work, but this
# is the preferred way.
# This line lets molter establish its hooks into interactions.py, allowing for
# its commands to work how they should.

# An important thing to note here is that you can set the default prefix or give
# an asynchronous function to generate prefixes via this.
# Look into default_prefix and generate_prefixes if you are interested in that.
# If neither of them are specified, molter will default to using the bot's mention
# as the prefix.

# There is also fetch_data_for_context - this will be talked more about in the
# advanced example, though it is recommended to keep it off unless you really need
# it.
molt = molter.Molter(bot)


# And this is how we declare message commands in our runner file.
# You can use message_command or msg_command to do this - they do the same thing.
# The decorator has a variety of options that you can use, but for this example,
# we're only using aliases - a way of allowing a command to be run under different
# commands.

# MolterContext is fundamentally different from interactions.py's Context,
# and the two are not compatible. Its purpose are to make using message commands
# easier.

# By default, commands are named after what their function's name is.
# They require a MolterContext argument, but everything else is left to you.
# In this example, we have a "a_number" argument that is typehinted as an integer.
# molter will automatically handle simple typehints like these, require the user
# to provide a number, and convert the input to an integer if it is.
# molter also handles some interactions.py classes, like User and Message.
@molt.message_command(aliases=["test2"])
async def test(ctx: molter.MolterContext, a_number: int):
    # MolterContext has a couple of QoL features, one being replying being as
    # simple as the below. ctx.message.reply does the same thing, if you wish.
    # Make sure that your content is a string - interactions.py does not
    # autoconvert given inputs into a string as of right now.
    await ctx.reply(str(a_number))


# Normal bot starting, not much to say here.
bot.start()