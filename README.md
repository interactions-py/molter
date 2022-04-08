[![PyPI](https://img.shields.io/pypi/v/interactions-molter)](https://pypi.org/project/interactions-molter/)
[![Downloads](https://static.pepy.tech/personalized-badge/interactions-molter?period=total&units=abbreviation&left_color=grey&right_color=green&left_text=pip%20installs)](https://pepy.tech/project/interactions-molter)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# interactions-molter
An extension library for interactions.py to add prefixed (AKA text-based or 'message') commands. Ported from [`dis-snek`'s `molter`](https://github.com/Discord-Snake-Pit/molter).

This attempts to make the prefixed command experience much like `discord.py`'s prefixed commands, though it is *not* 1:1 on purpose.

**NOTE**: This is a work in progress! Some things may be broken, and some things may not work as they should. More features need to be added, too.

**NOTE 2**: This extension is primarily developed by Astrea49. Direct questions about this to her, please!

## Installation

```
pip install interactions-molter
```

## Example

### Standalone

```python
import interactions
from interactions.ext import molter

client = interactions.Client(
    token="TOKEN",
    intents=interactions.Intents.DEFAULT | interactions.Intents.GUILD_MESSAGE_CONTENT,
)
molt = molter.setup(client)


@molt.prefixed_command(aliases=["test2"])
async def test(ctx: molter.MolterContext, some_var: int):
    await ctx.reply(str(some_var))


client.start()
```

### Extension

```python
import interactions
from interactions.ext import molter

# very important to use the below instead of Extension
# prefixed commands will not work otherwise
class Extend(molter.MolterExtension):
    def __init__(self, client: interactions.Client):
        self.client = client

    @molter.prefixed_command()
    async def soup(self, ctx: molter.MolterContext):
        await ctx.reply("give soup")

def setup(client: interactions.Client):
    Extend(client)
```

### Other examples

To view more examples and understand how `molter` works, take a look at the [`examples`](https://github.com/interactions-py/molter/tree/main/examples) folder in this repository.

## Credit

Thanks to both [`dis-snek`](https://github.com/Discord-Snake-Pit/Dis-Snek) and [Toricane's `interactions-message-commands`](https://github.com/Toricane/interactions-message-commands) for a decent part of this! They both had a huge influence over how this port was designed.

## TODO
- Add in documentation, or at least fill out docstrings.
