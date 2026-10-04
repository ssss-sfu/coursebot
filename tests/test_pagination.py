from unittest.mock import AsyncMock, Mock

import discord
import pytest

from src.courses.pagination import EmbedPaginator, send_pages

OWNER = 111


def pages(n):
  return [discord.Embed(title=f"Page {i + 1}") for i in range(n)]


def click(user_id=OWNER):
  interaction = Mock()
  interaction.user.id = user_id
  interaction.response.edit_message = AsyncMock()
  interaction.response.send_message = AsyncMock()
  return interaction


def shown(interaction):
  return interaction.response.edit_message.call_args.kwargs["embed"].title


@pytest.mark.asyncio
async def test_next_and_previous_move_between_pages():
  view = EmbedPaginator(pages(3), owner_id=OWNER)
  interaction = click()
  await view.next_page.callback(interaction)
  assert shown(interaction) == "Page 2"
  await view.next_page.callback(interaction)
  assert shown(interaction) == "Page 3"
  assert view.next_page.disabled and not view.previous_page.disabled
  await view.previous_page.callback(interaction)
  assert shown(interaction) == "Page 2"
  assert interaction.response.edit_message.call_args.kwargs["view"] is view


@pytest.mark.asyncio
async def test_only_the_command_user_can_page():
  view = EmbedPaginator(pages(3), owner_id=OWNER)
  assert await view.interaction_check(click(OWNER)) is True
  stranger = click(222)
  assert await view.interaction_check(stranger) is False
  stranger.response.send_message.assert_awaited_once()
  assert stranger.response.send_message.call_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_timeout_disables_buttons_and_updates_message():
  view = EmbedPaginator(pages(3), owner_id=OWNER)
  view.message = Mock()
  view.message.edit = AsyncMock()
  await view.on_timeout()
  assert all(item.disabled for item in view.children)
  view.message.edit.assert_awaited_once_with(view=view)


@pytest.mark.asyncio
async def test_send_pages_single_page_has_no_view():
  interaction = Mock()
  interaction.followup.send = AsyncMock()
  [page] = pages(1)
  await send_pages(interaction, [page])
  interaction.followup.send.assert_awaited_once_with(embed=page)


@pytest.mark.asyncio
async def test_send_pages_multiple_attaches_paginator_and_keeps_message():
  interaction = Mock()
  interaction.user.id = OWNER
  message = Mock()
  interaction.followup.send = AsyncMock(return_value=message)
  embeds = pages(3)
  await send_pages(interaction, embeds)
  call = interaction.followup.send.call_args
  view = call.kwargs["view"]
  assert call.kwargs["embed"] is embeds[0]
  assert view.owner_id == OWNER
  assert view.message is message
