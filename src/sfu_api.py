import json
import time
from collections.abc import Awaitable, Callable

import aiohttp


class SFUApiError(Exception):
  def __init__(self, message: str, status: int | None = None):
    super().__init__(message)
    self.status = status  # HTTP status, or None for timeouts / network / bad JSON


class SFUClient:
  def __init__(
    self, session: aiohttp.ClientSession, base_url: str, reviews_ttl: float = 3600, departments_ttl: float = 86400
  ):
    self._session = session
    self._base_url = base_url.rstrip("/")
    self._reviews_ttl = reviews_ttl
    self._departments_ttl = departments_ttl
    self._cache: dict[str, tuple[float, list]] = {}

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

  async def _cached(self, key: str, ttl: float, fetch: Callable[[], Awaitable[list]]) -> list:
    """Return a cached list if it's younger than `ttl`; empty results and errors are never cached."""
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

  async def get_departments(self) -> list[str]:
    # there's no departments endpoint; every outline (~3,600, ~3 MB) carries its dept code
    async def fetch():
      outlines = await self.get_json("/v1/rest/outlines") or []
      return sorted({o["dept"] for o in outlines if o.get("dept")})

    return await self._cached("departments", self._departments_ttl, fetch)
