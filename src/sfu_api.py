import json
import time

import aiohttp


class SFUApiError(Exception):
  def __init__(self, message: str, status: int | None = None):
    super().__init__(message)
    self.status = status  # HTTP status, or None for timeouts / network / bad JSON


class SFUClient:
  def __init__(self, session: aiohttp.ClientSession, base_url: str, reviews_ttl: float = 3600):
    self._session = session
    self._base_url = base_url.rstrip("/")
    self._reviews_ttl = reviews_ttl
    self._reviews: list | None = None
    self._reviews_fetched_at = 0.0

  async def get_json(self, path: str, params: dict | None = None):
    url = f"{self._base_url}{path}"
    try:
      async with self._session.get(url, params=params) as resp:
        if resp.status == 404:
          return None
        if resp.status != 200:
          raise SFUApiError(f"SFU Courses API returned {resp.status} for {path}", status=resp.status)
        return await resp.json()
    except SFUApiError:
      raise
    except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as error:
      raise SFUApiError(f"SFU Courses API request failed for {path}: {error!r}") from error

  async def get_instructor_reviews(self) -> list:
    now = time.monotonic()
    if self._reviews is not None and now - self._reviews_fetched_at < self._reviews_ttl:
      return self._reviews
    data = await self.get_json("/v1/rest/reviews/instructors") or []
    if data:
      self._reviews = data
      self._reviews_fetched_at = now
    return data
