<p align="center">
  <img src="https://cdn.discordapp.com/attachments/623677414278561793/978141383804215317/interactions-molter-banner.png" alt="The banner for molter for interactions.py." width="700"/>
</p>

<h1 align="center">Molter for interactions.py.</h1>

<p align="center">
  <a href="https://pypi.org/project/interactions-molter/">
    <img src="https://img.shields.io/pypi/v/interactions-molter" alt="PyPI">
  </a>
  <a href="https://pepy.tech/project/interactions-molter">
    <img src="https://static.pepy.tech/personalized-badge/interactions-molter?period=total&units=abbreviation&left_color=grey&right_color=green&left_text=pip%20installs" alt="Downloads">
  </a>
  <a href="https://github.com/psf/black">
    <img src="https://img.shields.io/badge/code%20style-black-000000.svg", alt="Code style: black">
  </a>
</p>


An extension library for interactions.py to add prefixed (AKA text-based or 'message') commands. This is a demonstration of [the molter framework](https://github.com/Astrea49/molter-core), a framework for adding prefixed commands into Discord Python libraries.

This attempts to make the prefixed command experience much like `discord.py`'s prefixed commands, though it is *not* 1:1 on purpose.

**NOTE**: This extension is primarily developed by Astrea49. Direct questions about this to her, please!

## Installation

```
pip install interactions-molter
```

## Examples

### Note

There are more in-depth examples about how `molter` works in the [`examples`](https://github.com/interactions-py/molter/tree/main/examples) folder in this repository. These can be considered the documentation for this extension as of right now, so please take a look at them!

### Standalone

```python
import interactions
from interactions.ext import molter

client = interactions.Client(
    token="TOKEN",
    intents=interactions.Intents.DEFAULT | interactions.Intents.GUILD_MESSAGE_CONTENT,
)
# See examples folder for more information.
# molter.setup(client, default_prefix="!")
molter.setup(client)


@molter.prefixed_command(aliases=["test2"])
async def test(ctx: molter.MolterContext, some_var: int):
    await ctx.reply(str(some_var))


client.start()
```

### Extension

```python
import interactions
from interactions.ext import molter

# very important to use the below instead of Extension
# it's a subclass of it, so application commands will work
# fine, but it's needed for prefixed commands to also work
class Extend(molter.MolterExtension):
    def __init__(self, client: interactions.Client):
        self.client = client

    @molter.prefixed_command()
    async def soup(self, ctx: molter.MolterContext):
        await ctx.reply("Give soup, please!")

def setup(client: interactions.Client):
    Extend(client)
```

## Branch Explanation

- The `main` branch is the PyPI version - this branch will never deviate from it. This is done to make sure the PyPI page's example links link to the right code.
- The `stable` branch is code considered code that is stable enough to use in daily use, though it is not perfect. This branch also will target any beta, pre-release, or release candidate version of `interactions.py`, if possible.
- The `dev` branch mirrors `interactions.py`'s `unstable` branch, and is also a general testing ground for new and experimental changes. *Bugs are common on this branch. If you decide to use this branch, I highly suggest pinning to a specific commit you know is stable.*

## Credit

Thanks to both [`NAFF`](https://github.com/NAFTeam/NAFF) and [Toricane's `interactions-message-commands`](https://github.com/Toricane/interactions-message-commands) for a decent part of this! They both had a huge influence over how this port was designed.