from dataclasses import dataclass
# using dataclasses to standardize the config
from datetime import timedelta
import os
from typing import Mapping

@dataclass(frozen=True) # immutable and hashable
class StudyTimeConfig:
  guild_id: int
  vc_channel_id: int
  text_channel_id: int
  moderation_channel_id: int
  role_name: str
  join_limit_count: int
  join_limit_window_s: int
  join_limit_window_td: timedelta
  short_stay_s: int
  short_stay_threshold: int
  short_stay_window_s: int
  short_stay_window_td: timedelta
  cleanup_interval_s: int=600

@dataclass(frozen=True)
class Config:
  discord_token: str
  study_time_config: StudyTimeConfig

def _int(env, name: str, default: int) -> int:
  raw = env.get(name)
  if raw is None or raw == "":
    return default
  try:
    return int(raw)
  except ValueError:
    raise RuntimeError(f"{name} must be an integer, got {raw} instead")


def load(env: Mapping[str, str] | None = None) -> Config:
  """
  SETUP:
  - Add custom role for STUDY_TIME_ROLE_NAME
  - Ensure bot role is above STUDY_TIME_ROLE_NAME
  """
  env = os.environ if env is None else env

  token = env.get('DISCORD_TOKEN')
  if token is None or token == "":
    raise RuntimeError("DISCORD_TOKEN is required")
  
  guild_id = _int(env, "GUILD_ID", 0)
  vc_channel_id = _int(env, "STUDY_TIME_VC_CHANNEL_ID", 0)
  vc_text_channel_id = _int(env, "STUDY_TIME_TEXT_CHANNEL_ID", 0)
  moderation_channel_id = _int(env, "MODERATION_REPORT_VC_CHANNEL_ID", 0)
  role_name = env.get("STUDY_TIME_ROLE_NAME", "")
  cleanup_interval_s = _int(env, "CLEANUP_INTERVAL_SECONDS", 600)
  join_limit_count = _int(env, "STUDY_TIME_VC_JOIN_LIMIT_COUNT", 5)
  join_limit_window_s = _int(env, "STUDY_TIME_VC_JOIN_LIMIT_WINDOW_SECONDS", 60)
  # Short-stay abuse detection: if a user has STUDY_TIME_VC_SHORT_STAY_THRESHOLD or more
  # visits shorter than STUDY_TIME_VC_SHORT_STAY_SECONDS within the tracking window,
  # they are blocked from receiving the role.
  short_stay_s = _int(env, "STUDY_TIME_VC_SHORT_STAY_SECONDS", 30)
  short_stay_threshold = _int(env, "STUDY_TIME_VC_SHORT_STAY_THRESHOLD", 5)
  short_stay_window_s = _int(env, "STUDY_TIME_VC_SHORT_STAY_WINDOW_SECONDS", 120)
  
  required = {
    "GUILD_ID": guild_id,
    "STUDY_TIME_VC_CHANNEL_ID": vc_channel_id,
    "STUDY_TIME_TEXT_CHANNEL_ID": vc_text_channel_id,
    "STUDY_TIME_ROLE_NAME": role_name,
    "MODERATION_REPORT_VC_CHANNEL_ID": moderation_channel_id,
  }
  missing = [name for name, value in required.items() if not value]
  if missing:
    raise RuntimeError(f"Invalid .env config: missing {', '.join(missing)}")

  non_zero_values = {
    "STUDY_TIME_VC_JOIN_LIMIT_COUNT": join_limit_count,
    "STUDY_TIME_VC_JOIN_LIMIT_WINDOW_SECONDS": join_limit_window_s,
    "STUDY_TIME_VC_SHORT_STAY_SECONDS": short_stay_s,
    "STUDY_TIME_VC_SHORT_STAY_THRESHOLD": short_stay_threshold,
    "STUDY_TIME_VC_SHORT_STAY_WINDOW_SECONDS": short_stay_window_s,
    "CLEANUP_INTERVAL_SECONDS": cleanup_interval_s,
  }
  for name, value in non_zero_values.items():
    if value <= 0:
      raise RuntimeError(f"Invalid .env config: {name} must be a positive integer, got {value}")

  if short_stay_s >= short_stay_window_s:
    raise RuntimeError(
      f"Invalid .env config: STUDY_TIME_VC_SHORT_STAY_SECONDS ({short_stay_s}) "
      f"must be less than STUDY_TIME_VC_SHORT_STAY_WINDOW_SECONDS ({short_stay_window_s})"
    )

  if join_limit_count >= join_limit_window_s:
    raise RuntimeError(
      f"Invalid .env config: STUDY_TIME_VC_JOIN_LIMIT_COUNT ({join_limit_count}) "
      f"must be less than STUDY_TIME_VC_JOIN_LIMIT_WINDOW_SECONDS ({join_limit_window_s})"
    )

  return Config(
    discord_token=token,
    study_time_config=StudyTimeConfig(
      guild_id=guild_id,
      vc_channel_id=vc_channel_id,
      text_channel_id=vc_text_channel_id,
      moderation_channel_id=moderation_channel_id,
      role_name=role_name,
      join_limit_count=join_limit_count,
      join_limit_window_s=join_limit_window_s,
      join_limit_window_td=timedelta(seconds=join_limit_window_s),
      short_stay_s=short_stay_s,
      short_stay_threshold=short_stay_threshold,
      short_stay_window_s=short_stay_window_s,
      short_stay_window_td=timedelta(seconds=short_stay_window_s),
      cleanup_interval_s=cleanup_interval_s,
    )
  )