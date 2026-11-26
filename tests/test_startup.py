from types import SimpleNamespace

import pytest
from aiohttp import test_utils

from src import config
from src.health import create_app
from src.main import CourseBot, is_newer_startup
from src.sfu_api import SFUClient


@pytest.mark.asyncio
async def test_health_check_answers_ok(session):
  server = test_utils.TestServer(create_app())
  await server.start_server()
  try:
    async with session.get(server.make_url("/health")) as resp:
      assert (resp.status, await resp.text()) == (200, "ok")
  finally:
    await server.close()


@pytest.mark.asyncio
async def test_course_bot_builds_and_handles_events(session, valid_env):
  bot = CourseBot(SFUClient(session, base_url="http://unused"), config.load(valid_env))
  assert bot.intents.members
  await bot.on_connect()
  await bot.on_disconnect()
  assert await bot.tree.interaction_check(None)
  bot.superseded = True
  assert not await bot.tree.interaction_check(None)


def voice(channel_id):
  return SimpleNamespace(channel=SimpleNamespace(id=channel_id, name="other") if channel_id else None)


@pytest.mark.asyncio
async def test_study_guard_ignores_other_voice_channels(session, valid_env):
  settings = config.load(valid_env)
  CourseBot(SFUClient(session, base_url="http://unused"), settings)  # a second bot in one process is fine now
  bot = CourseBot(SFUClient(session, base_url="http://unused"), settings)
  member = SimpleNamespace(id=1, name="m")
  # roles never synced and the bot isn't logged in: anything past the early return would raise
  await bot.study_guard.on_voice_state_update(member, voice(None), voice(99))
  await bot.study_guard.on_voice_state_update(member, voice(99), voice(None))
  assert not bot.study_guard.policy.joins


def message(id, author=1, content="[STUDY TIME]: study time should be working now..."):
  return SimpleNamespace(id=id, author=SimpleNamespace(id=author), content=content)


MINE = message(100)


@pytest.mark.parametrize(
  ("other", "newer"),
  [
    (message(200), True),  # a newer copy of this bot announced itself
    (message(100), False),  # our own startup message
    (message(50), False),  # an older announcement
    (message(200, author=2), False),  # another user posting the same text
    (message(200, content="[STUDY TIME]: restarting for an update..."), False),
  ],
)
def test_is_newer_startup(other, newer):
  assert is_newer_startup(other, MINE) is newer


def test_not_superseded_before_announcing():
  assert is_newer_startup(message(200), None) is False
