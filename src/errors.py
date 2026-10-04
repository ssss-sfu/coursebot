import traceback

import discord
from discord import app_commands

GENERIC_ERROR = "Something went wrong running that command. Try again in a bit."


async def handle_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
  """Last-resort handler for exceptions a slash command didn't catch itself."""
  name = interaction.command.name if interaction.command else "unknown"
  print(f"/{name} raised an unhandled error:")
  traceback.print_exception(error)  # prints "Traceback", so the CloudWatch alarm still fires
  try:
    if interaction.response.is_done():
      await interaction.followup.send(GENERIC_ERROR, ephemeral=True)
    else:
      await interaction.response.send_message(GENERIC_ERROR, ephemeral=True)
  except discord.HTTPException:
    pass  # the interaction expired or Discord is unreachable; the traceback above is the record
