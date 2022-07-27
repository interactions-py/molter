import traceback

import interactions
from interactions.ext import molter

# Nothing that wasn't seen in extension.py...
class ErrorDemonstration(molter.MolterExtension):
    def __init__(self, client: interactions.Client):
        self.client = client

    # There are three levels of errors in molter:
    # 1. A "global"/bot-wide "on_molter_command_error" event.
    # 2. An extension-wide "on_molter_command_error" function.
    # 3. A command specific error function.
    # Let's demonstrate all three quickly.

    # This is the global event, which is called for all molter command
    # errors that don't have any other error handler.
    # While this won't trigger from any commands in this extension,
    # if another command in another place errors out, the below will trigger.

    # All of the error handlers take in a MolterContext and the error itself.
    @interactions.extension_listener(name="on_molter_command_error")
    async def on_cmd_error(self, ctx: molter.MolterContext, error: Exception):
        print("Uh oh! A global error happened.")
        traceback.print_exception(type(error), error, error.__traceback__)

    # This registers an error handler for a MolterExtension.
    # There can only be one error handler per extension.
    @molter.ext_error_handler()
    async def on_molter_command_error(
        self, ctx: molter.MolterContext, error: Exception
    ):
        print("Uh oh! An extension-wide error happened.")
        traceback.print_exception(type(error), error, error.__traceback__)

    # Right, now here's a basic command that'll always error and its error handler.
    @molter.prefixed_command()
    async def always_error(self, ctx: molter.MolterContext):
        raise molter.BadArgument("Oops, I errored out!")

    # This is similar to how error handling is done with the main library and
    # commands there - that's why the naming is slightly different.
    @always_error.error
    async def always_error_error(self, ctx: molter.MolterContext, error: Exception):
        print(f"Uh oh! An error happened in {ctx.command.qualified_name}.")
        traceback.print_exception(type(error), error, error.__traceback__)

    # Now, if we run the "always_error" command, we'll see the above error handler
    # trigger, but not any of the others.

    # This will also always error out, but trigger the error handler for the extension
    # as it has no error handler of it own.
    @molter.prefixed_command()
    async def ext_always_error(self, ctx: molter.MolterContext):
        raise molter.BadArgument("Oops, I errored out!")


# Nothing new here in terms of extensions.
def setup(client: interactions.Client):
    ErrorDemonstration(client)
