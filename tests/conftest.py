import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import test_utils, web

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_env():
  return {
    'DISCORD_TOKEN': 'token',
    'GUILD_ID': '1',
    'STUDY_TIME_VC_CHANNEL_ID': '2',
    'STUDY_TIME_TEXT_CHANNEL_ID': '3',
    'MODERATION_REPORT_VC_CHANNEL_ID': '4',
    'STUDY_TIME_ROLE_NAME': 'Study Time',
  }


@pytest.fixture
def load_fixture():
  """Load a real SFU API response saved in tests/fixtures/, e.g. load_fixture("sections_cmpt225")."""

  def _load(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text())

  return _load


class FakeSFUApi:
  """Local stand-in for api.sfucourses.com: queue responses, then inspect the requests it received."""

  def __init__(self):
    self.queued: list[Callable[[], web.StreamResponse]] = []
    self.requests: list[web.Request] = []
    self.base_url = ""

  def respond(self, factory: Callable[[], web.StreamResponse]):
    self.queued.append(factory)

  async def handle(self, request: web.Request) -> web.StreamResponse:
    self.requests.append(request)
    if not self.queued:
      return web.Response(status=599, text="unexpected request: nothing queued")
    response = self.queued.pop(0)()
    if asyncio.iscoroutine(response):
      response = await response
    return response


@pytest_asyncio.fixture
async def api():
  fake = FakeSFUApi()
  app = web.Application()
  app.router.add_get("/{tail:.*}", fake.handle)
  server = test_utils.TestServer(app)
  await server.start_server()
  fake.base_url = str(server.make_url("/")).rstrip("/")
  yield fake
  await server.close()


@pytest_asyncio.fixture
async def session():
  async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as s:
    yield s
