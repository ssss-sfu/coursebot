import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp


class SFUApiError(Exception):
  def __init__(self, message: str, status: int | None = None):
    super().__init__(message)
    self.status = status  # HTTP status, or None for timeouts / network / bad JSON


class SFUClient:
  def __init__(
    self, session: aiohttp.ClientSession, base_url: str, reviews_ttl: float = 3600, outlines_ttl: float = 86400
  ):
    self._session = session
    self._base_url = base_url.rstrip("/")
    self._reviews_ttl = reviews_ttl
    self._outlines_ttl = outlines_ttl
    self._cache: dict[str, tuple[float, Any]] = {}

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

  async def _cached(self, key: str, ttl: float, fetch: Callable[[], Awaitable[Any]]) -> Any:
    """Return a cached value if it's younger than `ttl`; empty results (None, [], {}) and errors are never cached."""
    now = time.monotonic()
    hit = self._cache.get(key)
    if hit is not None and now - hit[0] < ttl:
      return hit[1]
    data = await fetch()
    if data:
      self._cache[key] = (now, data)
    return data

  async def get_instructor_reviews(self) -> list:
    async def fetch():
      return await self.get_json("/v1/rest/reviews/instructors") or []

    return await self._cached("reviews", self._reviews_ttl, fetch)

  async def get_all_outlines(self) -> list[dict]:
    """Every course outline (~3,600 courses, ~3 MB); shared by department autocomplete, /unlocks and /find."""

    async def fetch():
      return await self.get_json("/v1/rest/outlines") or []

    return await self._cached("outlines", self._outlines_ttl, fetch)

  async def get_departments(self) -> list[str]:
    # there's no departments endpoint; every outline carries its dept code
    return sorted({o["dept"] for o in await self.get_all_outlines() if o.get("dept")})
