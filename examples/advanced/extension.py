import datetime
from typing import Optional

from typing_extensions import Annotated

import interactions
from interactions.ext import molter


# Welcome to custom converters!
# You can subclass MolterConverter to do whatever you wish.
# All converters must have an asynchronous "convert" function that takes in
# the context and an argument.
# From there, you can do what you want, really.
class JudgementConverter(molter.MolterConverter):
    async def convert(self, ctx: molter.MolterContext, argument: str):
        return f"{ctx.author.mention} is {argument}."


# Converters in general follow a similar methodology to discord.py 1.7.3.
# As so, using the converter guide it has can at least help you out a little.
# Thinking converters are 1:1 to discord.py's converters is a bad idea, but
# you can kind of see how they could work and play with them from there.
# This includes Optional and Greedy, which are in molter.
# https://discordpy.readthedocs.io/en/v1.7.3/ext/commands/commands.html#converters


# Just another converter we'll be using later.
class DateTimeConverter(molter.MolterConverter):
    async def convert(self, ctx: molter.MolterContext, argument: str):
        return datetime.datetime.fromisoformat(argument)


# Hopefully this throws you off a bit looking at this for the first time.
# Extensions, normally, would not work for molter due to a variety of technical
# reasons. We can make molter commands work by using the MolterExtension class
# however, as it adds the necessary code and injects to make them work.
# MolterExtension is a subclass of Extension, so application commands will work
# with it, too, just as if it were a normal extension.
class Extension(molter.MolterExtension):
    def __init__(self, client: interactions.Client):
        self.client = client

    # First off - you'll notice how the way to declare a prefixed command
    # is different in extensions - this is just due to how extensions (and any similar
    # system) are. Just use this method in extensions and the other method in the main
    # file and you'll be good.

    # Second, you can see us using the converter here.
    # It should be noted that you can do something as simple as
    # "judgment: JudgementConverter" to use a converter, but using Annotated (possible
    # in Python 3.8 via typing_extensions - installed as a requirement when installing
    # molter - or on 3.9+ simply via typing) allows us to properly typehint this
    # function without making our static type checker complain.
    # More details about Annotated can be found here:
    # https://docs.python.org/3/library/typing.html#typing.Annotated

    # molter has support for Annotated, although it only works for Annotated types
    # with two arguments in them - it will error out if more are provided.
    # You may also use other ways of making your type checker happy rather than just
    # use Annotated, if you desire.
    @molter.prefixed_command()
    async def random_role(
        self, ctx: molter.MolterContext, judgment: Annotated[str, JudgementConverter]
    ):
        await ctx.reply(judgment)

    # One of the many other ways, and admittedly one of the cool ways, is by using
    # register_converter, which allows to you to "register" a converter for a type.
    # It's hard to explain in words, so just see this example:
    @molter.prefixed_command()
    @molter.register_converter(datetime.datetime, DateTimeConverter)
    async def convert_date(
        self, ctx: molter.MolterContext, datetime: datetime.datetime
    ):
        # This will output the date given in the viewing user's timezone. Thanks Discord!
        await ctx.reply(f"Date passed: <t:{datetime.timestamp()}:f>")

    # Anyways, molter will now know that the datetime type is meant to use DateTimeConverter
    # to convert a string argument to a datetime. This allows for very nice typehinting.
    # While not shown here, there is globally_register_converter if you want to do the same
    # thing but for EVERY molter command registered after the converter is registed.

    # Just a quick example of Optional here.
    # If an argument is marked as optional and has no default value, it'll returns None
    # if it can't convert whatever argument it sees (or if there's no argument at all).
    # Otherwise, if an argument has a default value, regardless of it its marked or not,
    # it'll return the default value if it can't convert.
    @molter.prefixed_command()
    async def optional_example(
        self, ctx: molter.MolterContext, maybe_int: Optional[int]
    ):
        if maybe_int:
            await ctx.reply(str(maybe_int))
        else:
            await ctx.reply("Hey, there's no integer here!")

    # And a quick example of Greedy.
    # To put it simply, Greedy will convert every new argument passed to it until it can't
    # anymore - for example, "!greedy_example 1124 124 23 e" would convert until the "e",
    # stop, and return a list of [1124, 124, 23].
    @molter.prefixed_command()
    async def greedy_example(
        self, ctx: molter.MolterContext, greedy_ints: molter.Greedy[int]
    ):
        greedy_int_strs = [str(i) for i in greedy_ints]
        await ctx.reply(" ".join(greedy_int_strs))


# Nothing new here in terms of extensions.
def setup(client: interactions.Client):
    Extension(client)
