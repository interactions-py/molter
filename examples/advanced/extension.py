from typing import Optional

import interactions
from interactions.ext import molter


# Welcome to custom converters!
# You can ou can subclass Converter to do whatever you wish.
# All converters must have an asynchronous convert function that takes in
# the context and an argument.
# From there, you can do what you want, really.
class JudgementConverter(molter.Converter):
    async def convert(self, ctx: molter.MolterContext, argument: str):
        return f"{ctx.author.mention} is {argument}."


# Converters in general follow a similar methodology to discord.py 1.7.3.
# As so, using the converter guide it has can at least help you out a little.
# Thinking converters are 1:1 to discord.py's converters is a bad idea, but
# you can kind of see how they could work and play with them from there.
# This includes Optional and Greedy, which are in molter if you wish.
# https://discordpy.readthedocs.io/en/v1.7.3/ext/commands/commands.html#converters

# Hopefully this throws you off a bit looking at this for the first time.
# Extensions, normally, would not work for molter due to a variety of technical
# reasons. We can make molter commands work by using the MolterExtension class
# however, as it adds the necessary code and injects to make them work.
class Extension(molter.MolterExtension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    # First off - you'll notice how the way to declare a molter/message command
    # is different in extensions - this is just due to how extensions (and any similar
    # system) are. Just use this method in extensions and the other method in the main
    # file and you'll be good.

    # Second, you can see us using the converter here. Yes, you can typehint it just
    # like that. Typehints will complain, though you can technically work around that
    # by using typing's TYPE_CHECKING or by subclassing Converter and whatever class
    # the final result is, to varying results.
    # molter does not and will not do this for you due to the multitude of ways of
    # doing it - it's up to you.
    @molter.msg_command()
    async def random_role(
        self, ctx: molter.MolterContext, judgment: JudgementConverter
    ):
        await ctx.reply(judgment)  # type: ignore

    # Just a quick example of Optional here.
    # If an argument is marked as optional and has no default value, it'll returns None
    # if it can't convert whatever argument it sees (or if there's no argument at all).
    # Otherwise, if an argument has a default value, regardless of it its marked or not,
    # it'll return the default value if it can't convert.
    @molter.msg_command()
    async def optional_example(
        self, ctx: molter.MolterContext, maybe_int: Optional[int]
    ):
        if maybe_int:
            await ctx.reply(str(maybe_int))
        else:
            await ctx.reply("Hey, there's no integer here!")

    # And a quick example of Greedy.
    # To put it simply, Greedy will convert every new argument passed to it until it can't
    # anymore - for example, "!greedy_example 1124 124 23 e" would convert until the e, stop,
    # and return a list of [1124, 124, 23].
    @molter.msg_command()
    async def greedy_example(
        self, ctx: molter.MolterContext, greedy_ints: molter.Greedy[int]
    ):
        greedy_int_strs = [str(i) for i in greedy_ints]
        await ctx.reply(" ".join(greedy_int_strs))


# Nothing new here in terms of extensions.
def setup(bot: interactions.Client):
    Extension(bot)
