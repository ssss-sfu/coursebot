import asyncio
import logging
import signal

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from src import config
from src.cogs.courses import Courses
from src.cogs.study_guard import StudyGuard, send_channel_message
from src.errors import handle_app_command_error
from src.health import run_health_server
from src.sfu_api import SFUClient

log = logging.getLogger(__name__)


class CourseTree(app_commands.CommandTree):
  async def interaction_check(self, interaction) -> bool:
    return not self.client.superseded


class CourseBot(commands.Bot):
  def __init__(self, sfu: SFUClient, settings: config.Config):
    intents = discord.Intents.default()
    intents.members = True
    super().__init__(command_prefix=commands.when_mentioned, intents=intents, tree_cls=CourseTree)
    self.sfu = sfu
    self.settings = settings
    self.tree.error(handle_app_command_error)
    self.startup_message = None
    self.superseded = False
    self.study_guard = StudyGuard(self, settings.study_time_config)

  async def setup_hook(self):
    await self.add_cog(Courses(self.sfu))
    await self.add_cog(self.study_guard)
    try:
      synced = await self.tree.sync()
    except discord.HTTPException:
      log.exception("Command sync failed; the commands from the last sync stay registered")
      return
    log.info("Synced %d command(s): %s", len(synced), ", ".join(cmd.name for cmd in synced))

  async def on_ready(self):
    log.info("Bot is online as %s", self.user)
    await self.study_guard.sync_roles()  # re-sync roles on every reconnect; joins/leaves can be missed while offline
    if self.startup_message is None:  # announce once per process, or a reconnect looks like a newer copy
      self.startup_message = await send_channel_message(
        self, self.settings.study_time_config.text_channel_id, 'study time should be working now...'
      )

  async def on_message(self, message):
    if is_newer_startup(message, self.startup_message):
      self.superseded = True
      log.info("newer copy is up, standing down")

  async def on_connect(self):
    log.info("Connected to Discord")

  async def on_disconnect(self):
    log.info("Disconnected from Discord")


# shortcut: if a deploy rolls back after the new copy announced itself, this copy ignores commands and Study Guard until the next deploy
def is_newer_startup(message, mine) -> bool:
  """True when `message` is another copy of this bot announcing itself after `mine` (ids grow over time)."""
  return (
    mine is not None
    and message.author.id == mine.author.id
    and message.id > mine.id
    and message.content == mine.content
  )


async def main():
  settings = config.load()

  async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
    sfu = SFUClient(session, base_url="https://api.sfucourses.com")
    bot = CourseBot(sfu, settings)

    runner = await run_health_server()
    try:
      loop = asyncio.get_running_loop()
      shutdown_event = asyncio.Event()
      for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_event.set)

      async with bot:
        bot_task = asyncio.create_task(bot.start(settings.discord_token))
        shutdown_task = asyncio.create_task(shutdown_event.wait())
        done, _ = await asyncio.wait({bot_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED)

        if shutdown_task in done:
          log.info("Received shutdown signal, shutting down")
          if not bot.superseded:  # a newer copy is already up; "restarting" would post after its "working now"
            await send_channel_message(
              bot,
              settings.study_time_config.text_channel_id,
              'restarting for an update... if study time is still broken in a few minutes, ping mehar',
            )
          bot_task.cancel()
          try:
            await bot_task
          except asyncio.CancelledError:
            pass
        else:
          bot_task.result()
    finally:
      await runner.cleanup()


if __name__ == "__main__":
  load_dotenv()
  logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
  asyncio.run(main())
