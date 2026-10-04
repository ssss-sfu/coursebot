import pytest

from src.config import load


def test_loads_valid_config(valid_env):
  cfg = load(valid_env)
  assert cfg.discord_token == 'token'
  assert cfg.study_time_config.guild_id == 1
  assert cfg.study_time_config.role_name == 'Study Time'


def test_defaults_applied_correctly(valid_env):
  cfg = load(valid_env)
  assert cfg.study_time_config.join_limit_count == 5
  assert cfg.study_time_config.join_limit_window_s == 60
  assert cfg.study_time_config.short_stay_s == 30
  assert cfg.study_time_config.short_stay_threshold == 5
  assert cfg.study_time_config.short_stay_window_s == 120
  assert cfg.study_time_config.cleanup_interval_s == 600


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


# {**valid_env, KEY: value} copies the valid config with one value changed
def test_non_integer_guild_id_raises_error(valid_env):
  with pytest.raises(RuntimeError, match='GUILD_ID'):
    load({**valid_env, 'GUILD_ID': 'abc'})


def test_non_positive_join_limit_count_raises_error(valid_env):
  with pytest.raises(RuntimeError, match='STUDY_TIME_VC_JOIN_LIMIT_COUNT'):
    load({**valid_env, 'STUDY_TIME_VC_JOIN_LIMIT_COUNT': '0'})


def test_short_stay_incorrect_boundaries_raises_error(valid_env):
  with pytest.raises(RuntimeError, match='STUDY_TIME_VC_SHORT_STAY_SECONDS'):
    load({**valid_env, 'STUDY_TIME_VC_SHORT_STAY_SECONDS': '200'})
