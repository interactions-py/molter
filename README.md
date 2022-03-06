# interactions-molter
Message commands in interactions.py! A port of [`dis-snek`'s `molter`](https://github.com/Discord-Snake-Pit/molter).

This attempts to make the message command experience much like `discord.py`'s message commands, though it is *not* 1:1 on purpose.

**NOTE**: This is a work in progress! Some things may be broken, and some things may not work as they should. More features need to be added, too.

## Installation

```
pip install git+https://github.com/Astrea49/interactions-molter.git
```

## Example

### Standalone

```python
import interactions
from interactions.ext import molter

bot = interactions.Client(
    token="TOKEN",
    intents=interactions.Intents.DEFAULT | interactions.Intents.GUILD_MESSAGE_CONTENT,
)
molt = molter.Molter(bot)


@molt.msg_command(aliases=["test2"])
async def test(ctx: molter.MolterContext, some_var: int):
    await ctx.reply(str(some_var))


bot.start()
```

### Extension

```python
import interactions
from interactions.ext import molter

# very important to use the below instead of Extension
# message commands will not work otherwise
class Extend(molter.MolterExtension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    @molter.msg_command()
    async def soup(self, ctx: molter.MolterContext):
        await ctx.reply("give soup")

def setup(bot: interactions.Client):
    Extend(bot)
```

## Credit

Thanks to both [`dis-snek`](https://github.com/Discord-Snake-Pit/Dis-Snek) and [Toricane's `interactions-message-commands`](https://github.com/Toricane/interactions-message-commands) for a decent part of this! They both had a huge influence over how this port was designed.

## TODO
- Add in converters for standard `interactions` objects.
- Add in documentation, or at least fill out docstrings.
