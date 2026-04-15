import os
import discord
from discord.ext import tasks
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

is_study_guard_initialized = False

load_dotenv()


def load_config() -> dict:
  """
  SETUP:
  - Add custom role for STUDY_TIME_ROLE_NAME
  - Ensure bot role is above STUDY_TIME_ROLE_NAME
  """
  guild_id = int(os.getenv("GUILD_ID", "0"))
  vc_channel_id = int(os.getenv("STUDY_TIME_VC_CHANNEL_ID", "0"))
  moderation_channel_id = int(os.environ.get("MODERATION_REPORT_VC_CHANNEL_ID", "0"))
  role_name = os.getenv("STUDY_TIME_ROLE_NAME", "")

  join_limit_count = int(os.getenv("STUDY_TIME_VC_JOIN_LIMIT_COUNT", "5"))
  join_limit_window_s = int(os.getenv("STUDY_TIME_VC_JOIN_LIMIT_WINDOW_SECONDS", "60"))

  # Short-stay abuse detection: if a user has STUDY_TIME_VC_SHORT_STAY_THRESHOLD or more
  # visits shorter than STUDY_TIME_VC_SHORT_STAY_SECONDS within the tracking window,
  # they are blocked from receiving the role.
  short_stay_s = int(os.getenv("STUDY_TIME_VC_SHORT_STAY_SECONDS", "30"))
  short_stay_threshold = int(os.getenv("STUDY_TIME_VC_SHORT_STAY_THRESHOLD", "5"))
  short_stay_window_s = int(os.getenv("STUDY_TIME_VC_SHORT_STAY_WINDOW_SECONDS", "120"))
  cleanup_interval_s = 600

  if not all([vc_channel_id, role_name, moderation_channel_id, guild_id]):
    raise RuntimeError("Invalid .env config")

  non_zero_values = {
    "STUDY_TIME_VC_JOIN_LIMIT_COUNT": join_limit_count,
    "STUDY_TIME_VC_JOIN_LIMIT_WINDOW_SECONDS": join_limit_window_s,
    "STUDY_TIME_VC_SHORT_STAY_SECONDS": short_stay_s,
    "STUDY_TIME_VC_SHORT_STAY_THRESHOLD": short_stay_threshold,
    "STUDY_TIME_VC_SHORT_STAY_WINDOW_SECONDS": short_stay_window_s,
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

  return {
    'STUDY_TIME_VC_CHANNEL_ID': vc_channel_id,
    'MODERATION_REPORT_VC_CHANNEL_ID': moderation_channel_id,
    'STUDY_TIME_ROLE_NAME': role_name,
    'CLEANUP_INTERVAL_SECONDS': cleanup_interval_s,
    'STUDY_TIME_VC_JOIN_LIMIT_COUNT': join_limit_count,
    'STUDY_TIME_VC_JOIN_LIMIT_WINDOW_SECONDS': join_limit_window_s,
    'STUDY_TIME_VC_JOIN_LIMIT_WINDOW_SECONDS_TIMEDELTA': timedelta(seconds=join_limit_window_s),
    'STUDY_TIME_VC_SHORT_STAY_SECONDS': short_stay_s,
    'STUDY_TIME_VC_SHORT_STAY_THRESHOLD_SECONDS': short_stay_threshold,
    'STUDY_TIME_VC_SHORT_STAY_WINDOW_SECONDS': short_stay_window_s,
    'STUDY_TIME_VC_SHORT_STAY_WINDOW_SECONDS_TIMEDELTA': timedelta(seconds=short_stay_window_s),
    'GUILD_ID': guild_id
  }


def format_eta(seconds: int) -> str:
  minutes, secs = divmod(seconds, 60)
  return f"{minutes}m {secs}s" if minutes > 0 else f"{secs}s"


def prune_timestamps(timestamps: list[datetime], window_start: datetime) -> list[datetime]:
  return [t for t in timestamps if t > window_start]


async def send_dm(member: discord.Member, message: str):
  try:
    await member.send(message)
  except:
    # Gracefully fail
    print(f'Encountered error sending message to user "{member.name}"')


async def send_channel_message(client: discord.Client, channelId: int, message: str):
  channel = client.get_channel(channelId)
  if channel and type(channel) == discord.TextChannel:
    await channel.send(f'[STUDY TIME] {message}')
  else:
    print(f'Failed to send message to channel {channelId}')


def setup(bot: discord.Client, config):
  global is_study_guard_initialized
  if is_study_guard_initialized:
    raise RuntimeError('This has already been called')
  is_study_guard_initialized = True
  
  guild_id = config['GUILD_ID']
  vc_channel_id = config['STUDY_TIME_VC_CHANNEL_ID']
  moderation_channel_id = config['MODERATION_REPORT_VC_CHANNEL_ID']
  role_name = config['STUDY_TIME_ROLE_NAME']
  join_limit_count = config['STUDY_TIME_VC_JOIN_LIMIT_COUNT']
  join_limit_window_s = config['STUDY_TIME_VC_JOIN_LIMIT_WINDOW_SECONDS']
  join_limit_window_td = config['STUDY_TIME_VC_JOIN_LIMIT_WINDOW_SECONDS_TIMEDELTA']
  short_stay_s = config['STUDY_TIME_VC_SHORT_STAY_SECONDS']
  short_stay_threshold = config['STUDY_TIME_VC_SHORT_STAY_THRESHOLD_SECONDS']
  short_stay_window_s = config['STUDY_TIME_VC_SHORT_STAY_WINDOW_SECONDS']
  short_stay_window_td = config['STUDY_TIME_VC_SHORT_STAY_WINDOW_SECONDS_TIMEDELTA']
  cleanup_interval_s = config['CLEANUP_INTERVAL_SECONDS']
  
  join_history: dict[int, list[datetime]] = defaultdict(list)
  short_stay_history: dict[int, list[datetime]] = defaultdict(list)
  user_joined_at: dict[int, datetime] = {}
  study_time_role = None


  @tasks.loop(seconds=cleanup_interval_s)
  async def cleanup_stale_history():
    # Avoid DoS or other weird stuff

    now = datetime.now(timezone.utc)

    join_window_start = now - join_limit_window_td
    short_stay_window_start = now - short_stay_window_td

    for user_id in list(join_history.keys()):
      join_history[user_id] = prune_timestamps(join_history[user_id], join_window_start)
      if not join_history[user_id]:
        del join_history[user_id]

    for user_id in list(short_stay_history.keys()):
      short_stay_history[user_id] = prune_timestamps(short_stay_history[user_id], short_stay_window_start)
      if not short_stay_history[user_id]:
        del short_stay_history[user_id]

    # Clean up user_joined_at entries older than the largest window
    stale_threshold = now - timedelta(seconds=max(join_limit_window_s, short_stay_window_s))
    for user_id in list(user_joined_at.keys()):
      if user_joined_at[user_id] < stale_threshold:
        del user_joined_at[user_id]


  async def on_ready(bot: discord.Client):
    nonlocal study_time_role

    if not cleanup_stale_history.is_running():
      cleanup_stale_history.start()

    guild = bot.get_guild(guild_id)
    study_time_vc = bot.get_channel(vc_channel_id)

    if guild and study_time_vc and type(study_time_vc) is discord.VoiceChannel:
      study_time_role = discord.utils.get(guild.roles, name=role_name)
      if not study_time_role:
        raise RuntimeError('Could not locate Study Time role')

      # Auto clear study time roles
      removed_roles = 0
      for member in guild.members:
        try:
          # only remove the study time role if they have the role and aren't currently in the Voice Channel
          if member.get_role(study_time_role.id) and member not in study_time_vc.members:
            removed_roles += 1
            await member.remove_roles(study_time_role)
        except Exception as e:
          print(e)

      # Auto assign role to all members in the VC
      added_roles = 0
      for member in study_time_vc.members:
        try:
          # if the member already has the role, we can save API calls
          if not member.get_role(study_time_role.id):
            added_roles += 1
            await member.add_roles(study_time_role)
        except Exception as e:
          print(e)
      
      await send_channel_message(
        bot,
        moderation_channel_id,
        f'Done initializing for Study Time. Auto assigned {study_time_role} role to {added_roles} members and removed from {removed_roles} other members.'
      )
        
    else:
      raise RuntimeError('Cannot initialize Study Time bot')
    

  @bot.event
  async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
  ):
    if not study_time_role:
      raise RuntimeError('Study Time Role is missing. Initialization failed')
    
    await bot.wait_until_ready()

    now = datetime.now(timezone.utc)
    new_channel_id = after.channel.id if after.channel else None
    old_channel_id = before.channel.id if before.channel else None
    is_joined = new_channel_id == vc_channel_id and old_channel_id != vc_channel_id
    is_left = old_channel_id == vc_channel_id and new_channel_id != vc_channel_id
    new_channel_name = after.channel.name if after.channel else None

    try:
      if is_joined:

        # Prune join history and check frequency limit
        join_history[member.id] = prune_timestamps(
          join_history[member.id], now - join_limit_window_td
        )

        # Check join frequency limit before recording this join (AVOID DoS)
        if len(join_history[member.id]) >= join_limit_count:
          oldest = join_history[member.id][0]
          remaining = max(1, int((oldest + join_limit_window_td - now).total_seconds()))
          moderation_message = f"{member.name} ({member.id}) exceeded join limit with timeout {format_eta(remaining)} ({join_limit_count} in {format_eta(join_limit_window_s)} to {new_channel_name})"

          await send_dm(
            member,
            f"You are joining Study Time too frequently. "
            f"Please wait {format_eta(remaining)} before rejoining to have access to the chat.",
          )
          await send_channel_message(bot, moderation_channel_id, moderation_message)
          return

        join_history[member.id].append(now)

        # Check short-stay abuse
        short_stay_history[member.id] = prune_timestamps(
          short_stay_history[member.id], now - short_stay_window_td
        )
        if len(short_stay_history[member.id]) >= short_stay_threshold:
          oldest = short_stay_history[member.id][0]
          remaining = max(1, int((oldest + short_stay_window_td - now).total_seconds()))
          moderation_message = f"{member.name} ({member.id}) flagged for short-stay abuse with timeout {format_eta(remaining)} ({len(short_stay_history[member.id])} short visits to {new_channel_name})"

          await send_dm(
            member,
            f"You have been joining Study Time for very short periods too often. "
            f"Please wait {format_eta(remaining)} before rejoining to have access to the chat.",
          )
          await send_channel_message(bot, moderation_channel_id, moderation_message)
          return

        user_joined_at[member.id] = now
        try:
          await member.add_roles(study_time_role)
        except Exception as e:
          await send_channel_message(bot, moderation_channel_id, f"[ERROR] Failed to add role {study_time_role.name} to {member.name} ({member.id}): {e}")

      elif is_left:
        # Record short stay if applicable
        join_time = user_joined_at.pop(member.id, None)
        short_stay_duration = (now - join_time).total_seconds() if join_time is not None else None
        if (short_stay_duration is not None) and (short_stay_duration < short_stay_s):
          short_stay_history[member.id] = prune_timestamps(
            short_stay_history[member.id], now - short_stay_window_td
          )
          short_stay_history[member.id].append(now)

        try:
          await member.remove_roles(study_time_role)
        except Exception as e:
          await send_channel_message(bot, moderation_channel_id, f"[ERROR] Failed to remove role ${study_time_role.name} from {member.name} ({member.id}): {e}")
    except Exception as error:
      await send_channel_message(bot, moderation_channel_id, f"[ERROR] An error occurred while processing role change: {error}")


  return {
    'on_ready': on_ready
  }
