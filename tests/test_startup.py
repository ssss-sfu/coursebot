import pytest
from aiohttp import test_utils

from src import config, study_guard
from src.health import create_app
from src.main import CourseBot
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
async def test_course_bot_builds_and_handles_events(session, valid_env, monkeypatch):
  monkeypatch.setattr(study_guard, "is_study_guard_initialized", False)  # setup() refuses a second call per process
  bot = CourseBot(SFUClient(session, base_url="http://unused"), config.load(valid_env))
  assert bot.intents.members
  await bot.on_connect()
  await bot.on_disconnect()
