import logging
from datetime import UTC, datetime

import discord
from discord.ext import commands, tasks

from src.config import StudyTimeConfig
from src.study_guard import JoinPolicy, format_eta

log = logging.getLogger(__name__)

BLOCK_DMS = {
  "join_limit": "You are joining Study Time too frequently.",
  "short_stay": "You have been joining Study Time for very short periods too often.",
}


async def send_dm(member: discord.Member, message: str):
  try:
    await member.send(message)
  except discord.HTTPException:
    log.warning('Failed to DM "%s"', member.name)


async def send_channel_message(client: discord.Client, channel_id: int, message: str):
  channel = client.get_channel(channel_id)
  if channel and isinstance(channel, discord.TextChannel):
    return await channel.send(f'[STUDY TIME]: {message}')
  log.warning('Failed to send message to channel %s', channel_id)
  return None


class StudyGuard(commands.Cog):
  """Gives the study-time role while a member is in the study-time voice channel, unless they're joining too often."""

  def __init__(self, bot: commands.Bot, cfg: StudyTimeConfig):
    self.bot = bot
    self.cfg = cfg
    self.policy = JoinPolicy.from_config(cfg)
    self.role: discord.Role | None = None

  async def cog_load(self):
    self.cleanup_loop.change_interval(seconds=self.cfg.cleanup_interval_s)
    self.cleanup_loop.start()

  async def cog_unload(self):
    self.cleanup_loop.cancel()

  @tasks.loop(seconds=600)  # replaced by CLEANUP_INTERVAL_SECONDS in cog_load
  async def cleanup_loop(self):
    self.policy.cleanup(datetime.now(UTC))

  async def report(self, message: str):
    await send_channel_message(self.bot, self.cfg.moderation_channel_id, message)

  async def sync_roles(self):
    """Give the role to everyone in the channel and take it from everyone else; joins/leaves are missed while offline."""
    guild = self.bot.get_guild(self.cfg.guild_id)
    channel = self.bot.get_channel(self.cfg.vc_channel_id)
    if not guild or type(channel) is not discord.VoiceChannel:
      raise RuntimeError('Cannot initialize Study Time bot')

    self.role = discord.utils.get(guild.roles, name=self.cfg.role_name)
    if not self.role:
      raise RuntimeError('Could not locate Study Time role')

    removed = 0
    for member in guild.members:
      if member.get_role(self.role.id) and member not in channel.members:
        removed += 1
        try:
          await member.remove_roles(self.role)
        except Exception:
          log.warning('Failed to remove the study time role from "%s"', member.name, exc_info=True)

    added = 0
    for member in channel.members:
      if not member.get_role(self.role.id):
        added += 1
        try:
          await member.add_roles(self.role)
        except Exception:
          log.warning('Failed to add the study time role to "%s"', member.name, exc_info=True)

    await self.report(
      f'Done initializing for Study Time. Auto assigned {self.role} role to {added} members '
      f'and removed from {removed} other members.'
    )

  @commands.Cog.listener()
  async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    vc_id = self.cfg.vc_channel_id
    new_id = after.channel.id if after.channel else None
    old_id = before.channel.id if before.channel else None
    joined = new_id == vc_id and old_id != vc_id
    left = old_id == vc_id and new_id != vc_id
    if not (joined or left) or self.bot.superseded:  # mute/deafen, other channels, or a newer copy is in charge
      return

    now = datetime.now(UTC)
    await self.bot.wait_until_ready()
    if not self.role:
      raise RuntimeError('Study Time Role is missing. Initialization failed')

    try:
      if joined:
        await self.handle_join(member, after.channel.name, now)
      else:
        self.policy.on_leave(member.id, now)
        try:
          await member.remove_roles(self.role)
        except Exception as e:
          await self.report(f"[ERROR] Failed to remove role {self.role.name} from {member.name} ({member.id}): {e}")
    except Exception as error:
      await self.report(f"[ERROR] An error occurred while processing role change: {error}")

  async def handle_join(self, member: discord.Member, channel_name: str, now: datetime):
    block = self.policy.on_join(member.id, now)
    if block is None:
      try:
        await member.add_roles(self.role)
      except Exception as e:
        await self.report(f"[ERROR] Failed to add role {self.role.name} to {member.name} ({member.id}): {e}")
      return

    wait = format_eta(block.wait_s)
    if block.reason == "join_limit":
      detail = f"exceeded join limit with timeout {wait} ({self.cfg.join_limit_count} in {format_eta(self.cfg.join_limit_window_s)} to {channel_name})"
    else:
      detail = f"flagged for short-stay abuse with timeout {wait} ({len(self.policy.short_stays[member.id])} short visits to {channel_name})"
    await send_dm(member, f"{BLOCK_DMS[block.reason]} Please wait {wait} before rejoining to have access to the chat.")
    await self.report(f"{member.name} ({member.id}) {detail}")
