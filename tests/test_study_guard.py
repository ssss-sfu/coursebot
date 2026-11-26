from datetime import UTC, datetime, timedelta

from src.study_guard import Block, JoinPolicy, prune_timestamps, wait_seconds

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
WINDOW = timedelta(seconds=60)


def make_policy():
  return JoinPolicy(
    join_limit=5,
    join_window=timedelta(seconds=60),
    short_stay=timedelta(seconds=30),
    short_stay_limit=5,
    short_stay_window=timedelta(seconds=120),
  )


def ago(seconds):
  return NOW - timedelta(seconds=seconds)


def test_under_the_limit_is_not_blocked():
  assert wait_seconds([ago(10)] * 4, NOW, WINDOW, limit=5) is None


def test_at_the_limit_waits_until_the_oldest_leaves_the_window():
  joins = [ago(s) for s in (50, 40, 30, 20, 10)]
  assert wait_seconds(joins, NOW, WINDOW, limit=5) == 10


def test_a_join_exactly_one_window_old_no_longer_counts():
  joins = prune_timestamps([NOW - WINDOW] + [ago(5)] * 4, NOW - WINDOW)
  assert wait_seconds(joins, NOW, WINDOW, limit=5) is None


def test_sixth_join_in_window_is_blocked():
  policy = make_policy()
  for s in (50, 40, 30, 20, 10):
    assert policy.on_join(1, ago(s)) is None
  assert policy.on_join(1, NOW) == Block("join_limit", 10)


def test_blocked_join_is_not_recorded():
  policy = make_policy()
  for s in (50, 40, 30, 20, 10):
    policy.on_join(1, ago(s))
  policy.on_join(1, NOW)
  assert len(policy.joins[1]) == 5  # spamming while blocked doesn't extend the block


def test_join_limit_is_per_user():
  policy = make_policy()
  for s in (50, 40, 30, 20, 10):
    policy.on_join(1, ago(s))
  assert policy.on_join(2, NOW) is None


def stay(policy, user_id, joined, seconds):
  policy.on_join(user_id, joined)
  policy.on_leave(user_id, joined + timedelta(seconds=seconds))


def test_too_many_short_stays_block_the_next_join():
  policy = make_policy()
  for start in (100, 80, 60, 40, 20):  # 5 visits of 5 s, spaced out so the join limit isn't hit
    stay(policy, 1, ago(start), 5)
  assert policy.on_join(1, NOW) == Block(
    "short_stay", 25
  )  # the oldest short stay (-95 s) leaves the 120 s window in 25 s


def test_a_visit_of_exactly_the_short_stay_time_is_not_short():
  policy = make_policy()
  for start in (100, 80, 60, 40, 20):
    stay(policy, 1, ago(start), 30)
  assert policy.short_stays.get(1, []) == []


def test_leave_without_a_recorded_join_records_nothing():
  policy = make_policy()
  policy.on_leave(1, NOW)  # e.g. the bot restarted while the member was in the channel
  assert policy.short_stays.get(1, []) == []


def test_cleanup_drops_old_entries_and_empty_users():
  policy = make_policy()
  stay(policy, 1, ago(500), 5)  # old: join, short stay and joined_at all past every window
  policy.on_join(2, ago(10))  # recent: still in the channel
  policy.cleanup(NOW)
  assert 1 not in policy.joins and 1 not in policy.short_stays
  assert policy.joins[2] == [ago(10)] and policy.joined_at == {2: ago(10)}
