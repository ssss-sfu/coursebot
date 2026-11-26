from datetime import UTC, datetime, timedelta

from src.study_guard import prune_timestamps, wait_seconds

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
WINDOW = timedelta(seconds=60)


def test_under_the_limit_is_not_blocked():
  assert wait_seconds([NOW - timedelta(seconds=10)] * 4, NOW, WINDOW, limit=5) is None


def test_at_the_limit_waits_until_the_oldest_leaves_the_window():
  joins = [NOW - timedelta(seconds=s) for s in (50, 40, 30, 20, 10)]
  assert wait_seconds(joins, NOW, WINDOW, limit=5) == 10


def test_a_join_exactly_one_window_old_no_longer_counts():
  joins = prune_timestamps([NOW - WINDOW] + [NOW - timedelta(seconds=5)] * 4, NOW - WINDOW)
  assert wait_seconds(joins, NOW, WINDOW, limit=5) is None
