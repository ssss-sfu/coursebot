import asyncio

import aiohttp
import pytest
from aiohttp import test_utils, web

from src.sfu_api import SFUApiError, SFUClient


# get_json
@pytest.mark.asyncio
async def test_success_returns_parsed_json(api, session):
  api.respond(lambda: web.json_response([{"dept": "CMPT", "number": "120"}]))
  data = await SFUClient(session, api.base_url).get_json("/v1/rest/outlines")
  assert data == [{"dept": "CMPT", "number": "120"}]


@pytest.mark.asyncio
async def test_params_reach_the_url(api, session):
  api.respond(lambda: web.json_response([]))
  await SFUClient(session, api.base_url).get_json("/v1/rest/outlines", params={"dept": "CMPT", "number": "105W"})
  request = api.requests[0]
  assert request.path == "/v1/rest/outlines"
  assert request.query["dept"] == "CMPT"
  assert request.query["number"] == "105W"


@pytest.mark.asyncio
async def test_params_are_url_encoded(api, session):
  api.respond(lambda: web.json_response([]))
  await SFUClient(session, api.base_url).get_json("/v1/rest/instructors", params={"name": "Brian Fraser & Co"})
  assert api.requests[0].query["name"] == "Brian Fraser & Co"


@pytest.mark.asyncio
async def test_base_url_trailing_slash_is_ignored(api, session):
  api.respond(lambda: web.json_response([]))
  await SFUClient(session, api.base_url + "/").get_json("/v1/rest/outlines")
  assert api.requests[0].path == "/v1/rest/outlines"


@pytest.mark.asyncio
async def test_404_returns_none(api, session):
  api.respond(lambda: web.Response(status=404))
  assert await SFUClient(session, api.base_url).get_json("/v1/rest/outlines") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 500, 503])
async def test_non_200_raises_with_status(api, session, status):
  api.respond(lambda: web.Response(status=status))
  with pytest.raises(SFUApiError) as exc:
    await SFUClient(session, api.base_url).get_json("/v1/rest/outlines")
  assert exc.value.status == status


@pytest.mark.asyncio
async def test_timeout_raises_without_status(api):
  async def slow():
    await asyncio.sleep(1)
    return web.json_response([])

  api.respond(slow)
  async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=0.1)) as fast_timeout:
    with pytest.raises(SFUApiError) as exc:
      await SFUClient(fast_timeout, api.base_url).get_json("/v1/rest/outlines")
  assert exc.value.status is None


@pytest.mark.asyncio
async def test_connection_error_raises_without_status(session):
  unused_port = test_utils.unused_port()
  with pytest.raises(SFUApiError) as exc:
    await SFUClient(session, f"http://127.0.0.1:{unused_port}").get_json("/v1/rest/outlines")
  assert exc.value.status is None


@pytest.mark.asyncio
async def test_invalid_json_raises(api, session):
  api.respond(lambda: web.Response(text="not json", content_type="application/json"))
  with pytest.raises(SFUApiError):
    await SFUClient(session, api.base_url).get_json("/v1/rest/outlines")


@pytest.mark.asyncio
async def test_non_json_content_type_raises(api, session):
  api.respond(lambda: web.Response(text="<html>maintenance</html>", content_type="text/html"))
  with pytest.raises(SFUApiError):
    await SFUClient(session, api.base_url).get_json("/v1/rest/outlines")


# get_instructor_reviews (cache)
@pytest.mark.asyncio
async def test_reviews_cached_within_ttl(api, session):
  api.respond(lambda: web.json_response([{"Name": "Brian Fraser"}]))
  client = SFUClient(session, api.base_url)
  first = await client.get_instructor_reviews()
  second = await client.get_instructor_reviews()
  assert first == second == [{"Name": "Brian Fraser"}]
  assert len(api.requests) == 1
  assert api.requests[0].path == "/v1/rest/reviews/instructors"


@pytest.mark.asyncio
async def test_reviews_refetched_after_ttl(api, session):
  api.respond(lambda: web.json_response([{"Name": "Old"}]))
  api.respond(lambda: web.json_response([{"Name": "New"}]))
  client = SFUClient(session, api.base_url, reviews_ttl=0)
  assert await client.get_instructor_reviews() == [{"Name": "Old"}]
  assert await client.get_instructor_reviews() == [{"Name": "New"}]
  assert len(api.requests) == 2


@pytest.mark.asyncio
async def test_reviews_empty_result_not_cached(api, session):
  api.respond(lambda: web.json_response([]))
  api.respond(lambda: web.json_response([{"Name": "Brian Fraser"}]))
  client = SFUClient(session, api.base_url)
  assert await client.get_instructor_reviews() == []
  assert await client.get_instructor_reviews() == [{"Name": "Brian Fraser"}]


@pytest.mark.asyncio
async def test_reviews_404_returns_empty_list(api, session):
  api.respond(lambda: web.Response(status=404))
  assert await SFUClient(session, api.base_url).get_instructor_reviews() == []


@pytest.mark.asyncio
async def test_reviews_error_propagates_and_is_not_cached(api, session):
  api.respond(lambda: web.Response(status=500))
  api.respond(lambda: web.json_response([{"Name": "Brian Fraser"}]))
  client = SFUClient(session, api.base_url)
  with pytest.raises(SFUApiError):
    await client.get_instructor_reviews()
  assert await client.get_instructor_reviews() == [{"Name": "Brian Fraser"}]
