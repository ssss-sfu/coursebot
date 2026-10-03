from datetime import timedelta

import pytest

from src.config import load


def test_loads_valid_config(valid_env):
  cfg = load(valid_env)
  assert cfg.discord_token == 'token'
  assert cfg.study_time_config.guild_id == 1
  assert cfg.study_time_config.role_name == 'Study Time'


@pytest.mark.parametrize(
  'name',
  [
    'GUILD_ID',
    'STUDY_TIME_VC_CHANNEL_ID',
    'STUDY_TIME_TEXT_CHANNEL_ID',
    'MODERATION_REPORT_VC_CHANNEL_ID',
    'STUDY_TIME_ROLE_NAME',
  ],
)
def test_missing_required_names_the_variables(valid_env, name):
  env = {key: value for key, value in valid_env.items() if key != name}
  with pytest.raises(RuntimeError, match=name):
    load(env)


def test_defaults_applied_correctly(valid_env):
  cfg = load(valid_env)
  assert cfg.study_time_config.join_limit_count == 5
  assert cfg.study_time_config.join_limit_window_s == 60
  assert cfg.study_time_config.short_stay_s == 30
  assert cfg.study_time_config.short_stay_threshold == 5
  assert cfg.study_time_config.short_stay_window_s == 120
  assert cfg.study_time_config.cleanup_interval_s == 600


def test_derived_time_deltas_correctly(valid_env):
  st = load(valid_env).study_time_config
  assert st.join_limit_window_td == timedelta(seconds=60)
  assert st.short_stay_window_td == timedelta(seconds=120)


def test_missing_token_raises_error():
  with pytest.raises(RuntimeError, match='DISCORD_TOKEN'):
    load({})


def test_several_missing_variables():
  with pytest.raises(RuntimeError) as exc:
    load({'DISCORD_TOKEN': 'token'})
  for name in [
    'GUILD_ID',
    'STUDY_TIME_VC_CHANNEL_ID',
    'STUDY_TIME_TEXT_CHANNEL_ID',
    'MODERATION_REPORT_VC_CHANNEL_ID',
    'STUDY_TIME_ROLE_NAME',
  ]:
    assert name in str(exc.value)


# **valid_env is a dictionary that is merged with the valid_env dictionary
# used to test specific values
def test_non_integer_guild_id_raises_error(valid_env):
  with pytest.raises(RuntimeError, match='GUILD_ID'):
    load({**valid_env, 'GUILD_ID': 'abc'})


def test_non_positive_join_limit_count_raises_error(valid_env):
  with pytest.raises(RuntimeError, match='STUDY_TIME_VC_JOIN_LIMIT_COUNT'):
    load({**valid_env, 'STUDY_TIME_VC_JOIN_LIMIT_COUNT': '0'})


def test_short_stay_incorrect_boundaries_raises_error(valid_env):
  with pytest.raises(RuntimeError, match='STUDY_TIME_VC_SHORT_STAY_SECONDS'):
    load({**valid_env, 'STUDY_TIME_VC_SHORT_STAY_SECONDS': '200'})


def test_join_limit_window_too_small_raises_error(valid_env):
  with pytest.raises(RuntimeError, match='STUDY_TIME_VC_JOIN_LIMIT_COUNT'):
    load({**valid_env, 'STUDY_TIME_VC_JOIN_LIMIT_COUNT': '60'})
