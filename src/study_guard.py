"""Study Guard rules: who may get the study-time role and when. No Discord here; the Cog in src/cogs/study_guard.py
calls this and does the talking."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import NamedTuple

from src.config import StudyTimeConfig


def format_eta(seconds: int) -> str:
  minutes, secs = divmod(seconds, 60)
  return f"{minutes}m {secs}s" if minutes > 0 else f"{secs}s"


def prune_timestamps(timestamps: list[datetime], window_start: datetime) -> list[datetime]:
  return [t for t in timestamps if t > window_start]


def wait_seconds(timestamps: list[datetime], now: datetime, window: timedelta, limit: int) -> int | None:
  """Seconds until the oldest of `limit` pruned timestamps leaves the window; None while under the limit."""
  if len(timestamps) < limit:
    return None
  return max(1, int((timestamps[0] + window - now).total_seconds()))


class Block(NamedTuple):
  reason: str  # "join_limit" or "short_stay"
  wait_s: int  # seconds until the member may join again


@dataclass
class JoinPolicy:
  join_limit: int
  join_window: timedelta
  short_stay: timedelta
  short_stay_limit: int
  short_stay_window: timedelta
  joins: dict[int, list[datetime]] = field(default_factory=lambda: defaultdict(list))
  short_stays: dict[int, list[datetime]] = field(default_factory=lambda: defaultdict(list))
  joined_at: dict[int, datetime] = field(default_factory=dict)

  @classmethod
  def from_config(cls, cfg: StudyTimeConfig) -> "JoinPolicy":
    return cls(
      join_limit=cfg.join_limit_count,
      join_window=cfg.join_limit_window_td,
      short_stay=timedelta(seconds=cfg.short_stay_s),
      short_stay_limit=cfg.short_stay_threshold,
      short_stay_window=cfg.short_stay_window_td,
    )

  def on_join(self, user_id: int, now: datetime) -> Block | None:
    """Record a join and return None, or return why the member is blocked (a blocked join isn't recorded)."""
    self.joins[user_id] = prune_timestamps(self.joins[user_id], now - self.join_window)
    remaining = wait_seconds(self.joins[user_id], now, self.join_window, self.join_limit)
    if remaining is not None:
      return Block("join_limit", remaining)
    self.joins[user_id].append(now)

    self.short_stays[user_id] = prune_timestamps(self.short_stays[user_id], now - self.short_stay_window)
    remaining = wait_seconds(self.short_stays[user_id], now, self.short_stay_window, self.short_stay_limit)
    if remaining is not None:
      return Block("short_stay", remaining)

    self.joined_at[user_id] = now
    return None

  def on_leave(self, user_id: int, now: datetime) -> None:
    """Count the visit as a short stay if it was shorter than `short_stay`."""
    joined = self.joined_at.pop(user_id, None)
    if joined is not None and now - joined < self.short_stay:
      self.short_stays[user_id] = prune_timestamps(self.short_stays[user_id], now - self.short_stay_window)
      self.short_stays[user_id].append(now)

  def cleanup(self, now: datetime) -> None:
    """Forget history that has left its window, so memory doesn't grow with every member who ever joined."""
    for history, window in ((self.joins, self.join_window), (self.short_stays, self.short_stay_window)):
      for user_id in list(history):
        history[user_id] = prune_timestamps(history[user_id], now - window)
        if not history[user_id]:
          del history[user_id]

    stale = now - max(self.join_window, self.short_stay_window)
    for user_id in [u for u, t in self.joined_at.items() if t < stale]:
      del self.joined_at[user_id]
