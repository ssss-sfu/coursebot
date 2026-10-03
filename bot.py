import asyncio
import re
import signal

import aiohttp
import discord
from aiohttp import web
from discord.ext import commands
from dotenv import load_dotenv

from src import config, study_guard
from src.sfu_api import SFUApiError, SFUClient

load_dotenv()


# helper function to parse term year
def parse_term_year(term_code: str):
  match = re.search(r'(\d{4})', term_code)
  return int(match.group(1)) if match else 0


# helper function to check the command type
def get_command_type(ctx: commands.Context) -> str:
  return 'slash' if ctx.interaction else 'prefix'


# Creates an instance of a client. This is our conneciton to discord.
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
intents.members = True  # Enable members intent
# Registers an event. This event is called when the bot has switched from offline to online.
bot = commands.Bot(command_prefix='!', intents=intents, case_insensitive=True)  # command handling


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


# Main Course Command
# Gets info about a course given subject and course number
# Can give optioanl arguments for Semester, Section, Instructor Userid, and Campus
@bot.hybrid_command(name='course', with_app_command=True, description="Get detailed info about a course")
async def get_outlines(ctx: commands.Context, subject: str, course_number: str):
  raw_number = course_number.strip()
  if not re.fullmatch(r'\d+[A-Za-z]*', raw_number):
    await ctx.send("Invalid course number format. Please use a format like '101' or '105W'.")
    return
  try:
    data = await sfu.get_json("/v1/rest/outlines", params={"dept": subject, "number": raw_number})
  except SFUApiError as err:
    print(f"/course failed: {err}")
    await ctx.send("An unexpected error occurred while fetching course outlines.")
    return
  if not data:
    if raw_number == "67":
      await ctx.send("67")
      return
    await ctx.send(f"No course data found for {subject.upper()} {course_number}.")
    return
  course = data[0]
  embed = discord.Embed(
    title=f"{course['dept']} {course['number']}: {course['title']}",
    description=course['description'],
    color=discord.Color.blue(),
  )

  offerings = course.get('offerings', [])
  if offerings:
    sorted_offerings = sorted(offerings, key=lambda x: parse_term_year(x.get('term', '')), reverse=True)
    recent_offerings = sorted_offerings[:4] if len(sorted_offerings) >= 4 else sorted_offerings
    offerings_list = []
    for offering in recent_offerings:
      term = offering.get('term', 'unknown')
      instructors = offering.get('instructors', [])
      if instructors:
        instructor_str = ", ".join(instructors)
        offerings_list.append(f"• **{term}** - Instructors: {instructor_str}")
      else:
        offerings_list.append(f"• **{term} - No instructors listed**")
    embed.add_field(name="Recent Offerings", value="\n".join(offerings_list), inline=False)
  else:
    embed.add_field(name="Recent Offerings Found", value="No offerings available", inline=False)
  embed.add_field(name="Credits", value=course['units'], inline=True)
  embed.add_field(name="Prerequisites", value=course['prerequisites'] or "None", inline=True)
  await ctx.send(embed=embed)


# Instructors Command
# Returns offerings of courses taught by a specific instructor
# Parameters: instructor full name
#   Returns an array of instructors + their offering
#   offering format: {department, course number, term, course title}
@bot.hybrid_command(name='offerings', with_app_command=True, description="Get course offerings by instructor")
async def get_offerings(ctx: commands.Context, instructor_name: str, term: str | None = None):
  try:
    data = await sfu.get_json("/v1/rest/instructors", params={"name": instructor_name})
  except SFUApiError as err:
    print(f"/offerings failed: {err}")
    embed = discord.Embed(
      title="Server Error",
      description="Couldn't reach the SFU Courses API. Try again later.",
      color=discord.Color.red(),
    )
    await ctx.send(embed=embed)
    return

  if not data:  # None (404) or [] (no match)
    embed = discord.Embed(
      title="No Instructors Found",
      description=f"No instructors found with the name '{instructor_name}'",
      color=discord.Color.red(),
    )
    embed.set_footer(text="Tip: Check your spelling or try using instructor's full name.")
    await ctx.send(embed=embed)
    return

  if len(data) > 1:
    instructor_list = "\n".join(f"• {instructor.get('name', 'Unknown')}" for instructor in data[:10])
    embed = discord.Embed(
      title="Multiple Instructors Found",
      description=f"Found {len(data)} instructors matching your search:",
      color=discord.Color.orange(),
    )
    embed.add_field(name="Matching Instructors:", value=instructor_list, inline=False)
    if get_command_type(ctx) == 'slash':
      embed.set_footer(text="Tip: If using /offerings, retry with the instructor's full name.")
    else:
      embed.set_footer(text="Tip: If using !offerings, use quotes around the full name.")
    await ctx.send(embed=embed)
    return

  instructor = data[0]
  name = instructor.get('name', 'Unknown')
  offerings = instructor.get('offerings', [])
  if term:
    offerings = [o for o in offerings if term.lower() in o.get('term', '').lower()]
    if not offerings:
      embed = discord.Embed(
        title="No Offerings Found for Specified Term",
        description=f"No offerings found for {name} in term '{term}'.",
        color=discord.Color.red(),
      )
      embed.add_field(name="Try:", value="• Check term spelling\n• Omit term to see all offerings\n", inline=False)
      await ctx.send(embed=embed)
      return

  offerings_list = [
    f"**{o.get('dept', 'N/A')} {o.get('number', 'N/A')}** - {o.get('title', 'N/A')} ({o.get('term', 'N/A')})"
    for o in offerings
  ]
  embed = discord.Embed(
    title=f"Courses taught by {name}",
    description="\n".join(offerings_list) if offerings_list else "No offerings found.",
    color=discord.Color.green(),
  )
  await ctx.send(embed=embed)


# Section Command
# Returns section info for a specific course in a specific year and term
# Parameters: year, term, department, course number
@bot.hybrid_command(
  name='section', with_app_command=True, description="Get specific course section for a specific year and term"
)
async def get_section(ctx: commands.Context, year: int, term: str, dept: str, number: str):
  try:
    data = await sfu.get_json("/v1/rest/sections", params={"term": f"{year}-{term}", "dept": dept, "number": number})
  except SFUApiError as err:
    print(f"/section failed: {err}")
    if err.status == 400:
      embed = discord.Embed(
        title="Try Again",
        description="Invalid query parameters. Please make sure you use YYYY-term format. Ex. 2026-spring",
        color=discord.Color.red(),
      )
    else:
      embed = discord.Embed(
        title="Server Error", description="Internal Server Error from not this bot lol", color=discord.Color.red()
      )
    await ctx.send(embed=embed)
    return

  if not data:
    embed = discord.Embed(
      title="No Sections Found",
      description=f"No sections found for {dept} {number} in {year}-{term}",
      color=discord.Color.red(),
    )
    await ctx.send(embed=embed)
    return

  course = data[0]
  embed = discord.Embed(
    title=f"{course['dept']} {course['number']}: {course['title']} ({year}-{term})",
    description=f"Units: {course['units']}",
    color=discord.Color.green(),
  )
  sections = course.get('sections', [])
  if sections:
    sections_info = []
    for section in sections:
      instrs = section.get('instructors', [])
      sections_info.append(
        f"**Section {section.get('section', 'N/A')}** - Instructors: {', '.join(instrs) if instrs else 'TBA'}"
        f" - Schedule: {section.get('schedule', 'TBA')}"
      )
    embed.add_field(name="Sections:", value="\n".join(sections_info), inline=False)
  else:
    embed.add_field(name="Sections:", value="No sections available", inline=False)
  await ctx.send(embed=embed)


# Reviews Command
# Returns a summary of review data for specified Instructor
# Parameters: Instructor full name
@bot.hybrid_command(name='reviews', with_app_command=True, description="Get reviews for a specific instructor")
async def get_reviews(ctx: commands.Context, instructor_name: str):
  try:
    data = await sfu.get_instructor_reviews()
  except SFUApiError as err:
    print(f"/reviews failed: {err}")
    embed = discord.Embed(
      title="Error", description="Failed to fetch reviews. Try again later.", color=discord.Color.red()
    )
    await ctx.send(embed=embed)
    return

  if not data:
    embed = discord.Embed(
      title="No Data Available",
      description="Could not retrieve instructor reviews at this time.",
      color=discord.Color.red(),
    )
    await ctx.send(embed=embed)
    return

  found_prof = next((s for s in data if s.get('Name', '').lower() == instructor_name.lower()), None)
  if not found_prof:
    embed = discord.Embed(
      title="No Reviews Found", description=f"No reviews found for '{instructor_name}'.", color=discord.Color.red()
    )
    embed.set_footer(text="Tip: Check spelling or try the instructor's full name.")
    await ctx.send(embed=embed)
    return
  url = found_prof.get('URL', '')
  embed = discord.Embed(
    title=f"Reviews for {found_prof.get('Name', instructor_name)}",
    description=f"Professor in the **{found_prof.get('Department', 'Unknown')}** department at SFU.",
    url=url or None,
    color=discord.Color.purple(),
  )
  embed.add_field(
    name="Information",
    value=f"• Rating: {float(found_prof.get('Quality', '0'))}/5\n"
    f"• Difficulty: {found_prof.get('Difficulty', 'N/A')}/5\n"
    f"• Ratings: {found_prof.get('Ratings', 'N/A')}\n"
    f"• {found_prof.get('WouldTakeAgain', 'N/A')} of students Would Take Again\n",
    inline=False,
  )
  await ctx.send(embed=embed)


async def main():
  global study_guard_client, settings, sfu
  settings = config.load()
  study_guard_client = study_guard.setup(bot, settings.study_time_config)

  async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
    sfu = SFUClient(session, base_url="https://api.sfucourses.com")

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
