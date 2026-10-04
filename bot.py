import asyncio
import signal

import aiohttp
import discord
from aiohttp import web
from discord.ext import commands
from dotenv import load_dotenv

from src import config, study_guard
from src.cogs.courses import Courses
from src.errors import handle_app_command_error
from src.sfu_api import SFUClient

load_dotenv()


# Creates an instance of a client. This is our conneciton to discord.
intents = discord.Intents.default()
intents.members = True  # Enable members intent
# Registers an event. This event is called when the bot has switched from offline to online.
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)
bot.tree.error(handle_app_command_error)


# async health check
async def health_check(request):
  return web.Response(text="ok", status=200)


async def run_health_server():
  app = web.Application()
  app.router.add_get('/', health_check)  # Root path for AWS App Runner default health check
  app.router.add_get('/health', health_check)
  runner = web.AppRunner(app)
  await runner.setup()
  site = web.TCPSite(runner, '0.0.0.0', 8080)
  await site.start()
  print("Health check server started on port 8080")


@bot.event
async def on_ready():
  print(f'Bot is online as {bot.user}')
  await study_guard_client.on_ready(bot)
  synced = await bot.tree.sync()
  print(f"Synced {len(synced)} command(s)")
  print("Available commands:", [cmd.name for cmd in synced])
  await study_guard.send_channel_message(
    bot, settings.study_time_config.text_channel_id, 'study time should be working now...'
  )


@bot.event
async def on_connect():
  print("Bot connected to Discord!")


@bot.event
async def on_disconnect():
  print("Bot disconnected from Discord!")


async def main():
  global study_guard_client, settings
  settings = config.load()
  study_guard_client = study_guard.setup(bot, settings.study_time_config)

  async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
    sfu = SFUClient(session, base_url="https://api.sfucourses.com")
    await bot.add_cog(Courses(sfu))

    # run the health server FIRST so App Runner health checks pass
    await run_health_server()
    print("Health check server is running on port 8080")

    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
      loop.add_signal_handler(sig, shutdown_event.set)

    async with bot:
      bot_task = asyncio.create_task(bot.start(settings.discord_token))
      shutdown_task = asyncio.create_task(shutdown_event.wait())
      done, _ = await asyncio.wait({bot_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED)

      if shutdown_task in done:
        print("Received shutdown signal. Shutting down...")
        await study_guard.send_channel_message(
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
  # leaving the session block closes the HTTP session, after the bot has shut down


if __name__ == '__main__':
  asyncio.run(main())
