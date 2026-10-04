from unittest.mock import AsyncMock, Mock

import discord
import pytest
from discord import app_commands

from src.errors import GENERIC_ERROR, handle_app_command_error


def make_interaction(*, already_responded: bool):
  interaction = Mock()
  interaction.command.name = "course"
  interaction.response.is_done = Mock(return_value=already_responded)
  interaction.response.send_message = AsyncMock()
  interaction.followup.send = AsyncMock()
  return interaction


def invoke_error():
  try:
    raise ValueError("boom")
  except ValueError as original:
    error = app_commands.AppCommandError("wrapped")
    error.__cause__ = original
    return error


@pytest.mark.asyncio
async def test_replies_directly_when_not_yet_responded():
  interaction = make_interaction(already_responded=False)
  await handle_app_command_error(interaction, invoke_error())
  interaction.response.send_message.assert_awaited_once_with(GENERIC_ERROR, ephemeral=True)
  interaction.followup.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_uses_followup_after_defer():
  interaction = make_interaction(already_responded=True)
  await handle_app_command_error(interaction, invoke_error())
  interaction.followup.send.assert_awaited_once_with(GENERIC_ERROR, ephemeral=True)
  interaction.response.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_prints_traceback_for_the_alarm(capsys):
  await handle_app_command_error(make_interaction(already_responded=True), invoke_error())
  err = capsys.readouterr().err
  assert "Traceback" in err
  assert "ValueError: boom" in err


@pytest.mark.asyncio
async def test_discord_failure_while_replying_is_swallowed():
  interaction = make_interaction(already_responded=True)
  interaction.followup.send.side_effect = discord.HTTPException(Mock(status=404, reason="Not Found"), "expired")
  await handle_app_command_error(interaction, invoke_error())  # must not raise


@pytest.mark.asyncio
async def test_unknown_command_name():
  interaction = make_interaction(already_responded=False)
  interaction.command = None
  await handle_app_command_error(interaction, invoke_error())
  interaction.response.send_message.assert_awaited_once()
