from dotenv import load_dotenv
import discord
from discord.ext import commands, tasks
from typing import Optional
import os 
import http.client
import json
import re
import urllib.parse
# health check imports
import asyncio
from aiohttp import web
from collections import defaultdict
from datetime import datetime, timezone, timedelta

load_dotenv()

"""
SETUP:
- Add custom role for TARGET_ROLE_NAME
- Ensure bot role is above TARGET_ROLE_NAME
"""

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
TARGET_VC_CHANNEL_ID = int(os.getenv("TARGET_VC_CHANNEL_ID", "0"))
TARGET_ROLE_NAME = os.getenv("TARGET_ROLE_NAME", "")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

JOIN_LIMIT_COUNT = int(os.getenv("JOIN_LIMIT_COUNT", "5"))
JOIN_LIMIT_WINDOW_SECONDS = int(os.getenv("JOIN_LIMIT_WINDOW_SECONDS", "60"))

# Short-stay abuse detection: if a user has SHORT_STAY_THRESHOLD or more
# visits shorter than SHORT_STAY_SECONDS within the tracking window,
# they are blocked from receiving the role.
SHORT_STAY_SECONDS = int(os.getenv("SHORT_STAY_SECONDS", "30"))
SHORT_STAY_THRESHOLD = int(os.getenv("SHORT_STAY_THRESHOLD", "5"))
SHORT_STAY_WINDOW_SECONDS = int(os.getenv("SHORT_STAY_WINDOW_SECONDS", "120"))
CLEANUP_INTERVAL_SECONDS = 600

if not all([DISCORD_BOT_TOKEN, TARGET_VC_CHANNEL_ID, TARGET_ROLE_NAME, GUILD_ID]):
    raise RuntimeError("Invalid .env config")


# helper function to parse term year
def parse_term_year(term_code: str):
  match = re.search(r'(\d{4})', term_code)
  return int(match.group(1)) if match else 0

#helper function to check the command type
def get_command_type(ctx: commands.Context) -> str:
  return 'slash' if ctx.interaction else 'prefix'

discord_token = os.getenv('DISCORD_TOKEN')

conn = http.client.HTTPSConnection("api.sfucourses.com")

# Creates an instance of a client. This is our conneciton to discord.
intents = discord.Intents.default() 
intents.message_content = True # Enable message content intent
# Registers an event. This event is called when the bot has switched from offline to online.
bot = commands.Bot(command_prefix='!', intents=intents, case_insensitive=True) # command handling

#async health check
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
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} command(s)")
    print("Available commands:", [cmd.name for cmd in synced])

    global target_guild, target_role
    target_guild = bot.get_guild(GUILD_ID)
    if not target_guild:
        print(f"Could not find guild from ID {GUILD_ID}, will retry on next ready event")
        return

    target_role = discord.utils.get(target_guild.roles, name=TARGET_ROLE_NAME)
    if not target_role:
        print(f"Could not find role from name {TARGET_ROLE_NAME}, will retry on next ready event")
        return

    if not cleanup_stale_history.is_running():
        cleanup_stale_history.start()

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
  # Considering courses that have alphanumeric course numbers (e.g., "105W")
  number = re.fullmatch(r'(\d+)([A-Za-z]*)', course_number.strip())
  if not number:
    await ctx.send("Invalid course number format. Please use a format like '101' or '105W'.")
    return
  raw_number = course_number.strip()
  # connects to SFUCourses API to get outlines for requested course
  conn.request("GET", f"/v1/rest/outlines?dept={subject}&number={raw_number}")
  # stores response from API
  response = conn.getresponse()
  
  if response.status == 200:
    outlines = response.read()
    if outlines == b'[]':
      await ctx.send(f"No course data found for {subject.upper()} {course_number}. Please try again.")
      return
    data = json.loads(outlines.decode('utf-8'))
    if not data:
      if course_number.strip() == "67":
        await ctx.send("67")
        return
      await ctx.send(f"No course data found for {subject.upper()} {course_number}.")
      return
    course = data[0]
    embed = discord.Embed(
      title=f"{course['dept']} {course['number']}: {course['title']}",
      description = course['description'],
      color=discord.Color.blue()
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
      embed.add_field(
        name="Recent Offerings",
        value="\n".join(offerings_list),
        inline=False
      )
    else:
      embed.add_field(
          name="Recent Offerings Found",
          value="No offerings available",
          inline=False
      )
    embed.add_field(name="Credits", value=course['units'], inline=True)
    embed.add_field(name="Prerequisites", value=course['prerequisites'] or "None", inline=True)
    await ctx.send(embed=embed)
  elif response.status == 404:
    await ctx.send(f"Error fetching course outlines: {response.status}")
  else:
    await ctx.send("An unexpected error occurred while fetching course outlines.")

# Instructors Command
# Returns offerings of courses taught by a specific instructor
# Parameters: instructor full name
#   Returns an array of instructors + their offering
#   offering format: {department, course number, term, course title}
@bot.hybrid_command(name='offerings', with_app_command=True, description="Get course offerings by instructor")
async def get_offerings(ctx: commands.Context, instructor_name: str, term: Optional[str] = None):
  encoded_name = urllib.parse.quote(instructor_name)
  conn.request("GET", f"/v1/rest/instructors?name={encoded_name}")
  response = conn.getresponse()
  
  if response.status == 200:
    data = json.loads(response.read().decode('utf-8'))
    if data:
      if len(data) > 1:
        instructor_names = [instructor.get('name', 'Unknown') for instructor in data]
        embed = discord.Embed(
          title="Multiple Instructors Found",
          description=f"Found {len(data)} instructors matching your search:",
          color=discord.Color.orange()
        )
        instructor_list = "\n".join(f"• {name}" for name in instructor_names[:10])
        embed.add_field(
          name="Matching Instructors:",
          value=instructor_list,
          inline=False
        )
        command_type = get_command_type(ctx)
        if command_type == 'slash':
          embed.set_footer(text="Tip: If using /instructor, retry with instructor's full name.")
        else:
          embed.set_footer(text="Tip: If using !instructor, use quotes around the full name.")
        await ctx.send(embed=embed)
        return
      embeds = []
      for instructor in data:
        instructor_name = instructor.get('name', 'Unknown')
        all_offerings = instructor.get('offerings', [])
        if term:
            filtered_offerings = [
              offering for offering in all_offerings
              if term.lower() in offering.get('term', '').lower()
            ]
            show_offerings = filtered_offerings
            if not show_offerings:
              embed = discord.Embed(
                title="No Offerings Found for Specified Term",
                description=f"No offerings found for {instructor_name} in term '{term}'.",
                color=discord.Color.red()
              )
              embed.add_field(
                name="Try:",
                value="• Check term spelling\n• Omit term to see all offerings\n",
                inline=False
              )
              embed.set_footer(text="Tip: Check term spelling or omit term to see all offerings.")
              embeds.append(embed)
              continue
        else:
          show_offerings = all_offerings
        offerings_list = [] 
        for offering in show_offerings:
          dept = offering.get('dept', 'N/A')
          number = offering.get('number', 'N/A')
          term = offering.get('term', 'N/A')
          title = offering.get('title', 'N/A')
          offerings_list.append(f"**{dept} {number}** - {title} ({term})")
        
        embed = discord.Embed(
          title=f"Courses taught by {instructor_name}",
          description="\n".join(offerings_list) if offerings_list else "No offerings found.",
          color=discord.Color.green()
        )
        embeds.append(embed)
      for embed in embeds[:10]:
          await ctx.send(embed=embed)
    else:
      # No instructors found
      embed = discord.Embed(
        title="No Instructors Found",
        description=f"No instructors found with the name '{instructor_name}'",
        color=discord.Color.red()
      )
      embed.set_footer(text="Tip: Check your spelling or try using instructor's full name.")
      await ctx.send(embed=embed)
  elif response.status == 404:
    embed = discord.Embed(
      title="Not Found",
      description="No instructors found",
      color=discord.Color.red()
    )
    await ctx.send(embed=embed)
  else:
    embed = discord.Embed(
      title="Server Error",
      description=f"Internal Server Error: {response.status}",
      color=discord.Color.red()
    )
    await ctx.send(embed=embed)

# Section Command
# Returns section info for a specific course in a specific year and term
# Parameters: year, term, department, course number
@bot.hybrid_command(name='section', with_app_command=True, description="Get specific course section for a specific year and term, ")
async def get_section(ctx: commands.Context, year: int, term: str, dept: str, number: str):
  conn.request("GET", f"/v1/rest/sections?term={year}-{term}&dept={dept}&number={number}")
  response = conn.getresponse()
  if response.status == 200:
    sections_list = response.read() # array of dept, number, sections array, term, title, and units
    data = json.loads(sections_list.decode('utf-8'))
    if not data:
      embed = discord.Embed(
        title="No Sections Found",
        description=f"No sections found for {dept} {number} in {year}-{term}",
        color=discord.Color.red()
      )
      await ctx.send(embed=embed)
      return
    course = data[0]
    embed = discord.Embed(
      title=f"{course['dept']} {course['number']}: {course['title']} ({year}-{term})",
      description=f"Units: {course['units']}",
      color=discord.Color.green()
    )
    sections = course.get('sections', [])
    if sections:
      sections_info = []
      for section in sections:
        sec_code = section.get('section', 'N/A')
        instrs = section.get('instructors', [])
        instrs_str = ", ".join(instrs) if instrs else "TBA"
        schedule = section.get('schedule', 'TBA')
        sections_info.append(f"**Section {sec_code}** - Instructors: {instrs_str} - Schedule: {schedule}")
      embed.add_field(
        name="Sections:",
        value="\n".join(sections_info),
        inline=False
      )
    else:
      embed.add_field(
        name="Sections:",
        value="No sections available",
        inline=False
      )
    await ctx.send(embed=embed)
  elif response.status==404:
    embed = discord.Embed(
      title="Not Found",
      description=f"No sections found for {dept} {number} in {year}-{term}",
      color=discord.Color.red()
    )
    await ctx.send(embed=embed)
    return
  elif response.status==400:
    embed=discord.Embed(
        title="Try Again",
        description="Invalid querey parameters. " \
        "Please make sure you use YYYY-term format. Ex. 2026-spring",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)
    return
  else:
    embed = discord.Embed(
      title="Server Error",
      description="Internal Server Error from not this bot lol",
      color=discord.Color.red()
    )
    await ctx.send(embed=embed)
  return

# Reviews Command
# Returns a summary of review data for specified Instructor
# Parameters: Instructor full name
@bot.hybrid_command(name='reviews', with_app_command=True, description="Get reviews for a specific instructor")
async def get_reviews(ctx:commands.Context, instructor_name: str):
  conn.request("GET", f"/v1/rest/reviews/instructors") # Grabs data for ALL instructors
  response=conn.getresponse()

  if response.status==200:
    #success
    data=json.loads(response.read().decode('utf-8'))
    if data:
      # Search for matching professor (case-insensitive)
      found_prof = None
      for summary in data:
        prof_name = summary.get('Name', '')
        if instructor_name.lower() == prof_name.lower():
          found_prof = summary
          break
      
      if found_prof:
        rating = float(found_prof.get('Quality', '0'))
        difficulty = found_prof.get('Difficulty', 'N/A')
        ratings_count = found_prof.get('Ratings', 'N/A')
        would_take_again = found_prof.get('WouldTakeAgain', 'N/A')
        department = found_prof.get('Department', 'Unknown')
        url = found_prof.get('URL', '')

        embed = discord.Embed(
          title=f"Reviews for {found_prof.get('Name', instructor_name)}",
          description=f"Professor in the **{department}** department at SFU.",
          url=url if url else None,
          color=discord.Color.purple()
        )
        embed.add_field(
          name="Information",
          value=f"• Rating: {rating}/5\n"
                f"• Difficulty: {difficulty}/5\n"
                f"• Ratings: {ratings_count}\n"
                f"• {would_take_again} of students Would Take Again\n",
          inline=False
        )
        await ctx.send(embed=embed)
      else:
        # No matching professor found
        embed = discord.Embed(
          title="No Reviews Found",
          description=f"No reviews found for '{instructor_name}'.",
          color=discord.Color.red()
        )
        embed.set_footer(text="Tip: Check spelling or try the instructor's full name.")
        await ctx.send(embed=embed)
    else:
      embed = discord.Embed(
        title="No Data Available",
        description="Could not retrieve instructor reviews at this time.",
        color=discord.Color.red()
      )
      await ctx.send(embed=embed)
  elif response.status == 500:
    embed = discord.Embed(
      title="Server Error",
      description=f"Internal Server Error: {response.status}",
      color=discord.Color.red()
    )
    await ctx.send(embed=embed)
  else:
    embed = discord.Embed(
      title="Error",
      description=f"Failed to fetch reviews: {response.status}",
      color=discord.Color.red()
    )
    await ctx.send(embed=embed)

#####

target_guild: Optional[discord.Guild] = None
target_role: Optional[discord.Role] = None
join_history: dict[int, list[datetime]] = defaultdict(list)
short_stay_history: dict[int, list[datetime]] = defaultdict(list)
user_joined_at: dict[int, datetime] = {}


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


@tasks.loop(seconds=CLEANUP_INTERVAL_SECONDS)
async def cleanup_stale_history():
    # Avoid DoS or other weird stuff
    print('Running GC on Study Time railguards')

    now = datetime.now(timezone.utc)
    join_window_start = now - timedelta(seconds=JOIN_LIMIT_WINDOW_SECONDS)
    short_stay_window_start = now - timedelta(seconds=SHORT_STAY_WINDOW_SECONDS)

    for user_id in list(join_history.keys()):
        join_history[user_id] = prune_timestamps(join_history[user_id], join_window_start)
        if not join_history[user_id]:
            del join_history[user_id]

    for user_id in list(short_stay_history.keys()):
        short_stay_history[user_id] = prune_timestamps(short_stay_history[user_id], short_stay_window_start)
        if not short_stay_history[user_id]:
            del short_stay_history[user_id]

    # Clean up user_joined_at entries older than the largest window
    stale_threshold = now - timedelta(seconds=max(JOIN_LIMIT_WINDOW_SECONDS, SHORT_STAY_WINDOW_SECONDS))
    for user_id in list(user_joined_at.keys()):
        if user_joined_at[user_id] < stale_threshold:
            del user_joined_at[user_id]


@bot.event
async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
):
    if not target_guild or not target_role or member.guild.id != target_guild.id:
        return

    now = datetime.now(timezone.utc)
    new_channel_id = after.channel.id if after.channel else None
    old_channel_id = before.channel.id if before.channel else None
    is_joined = new_channel_id == TARGET_VC_CHANNEL_ID and old_channel_id != TARGET_VC_CHANNEL_ID
    is_left = old_channel_id == TARGET_VC_CHANNEL_ID and new_channel_id != TARGET_VC_CHANNEL_ID

    try:
        if is_joined:
            print(f"{member.id} joined {new_channel_id} @ {now}")
            user_joined_at[member.id] = now

            # Prune join history and check frequency limit
            join_history[member.id] = prune_timestamps(
                join_history[member.id], now - timedelta(seconds=JOIN_LIMIT_WINDOW_SECONDS)
            )

            # Check join frequency limit before recording this join (AVOID DoS)
            if len(join_history[member.id]) >= JOIN_LIMIT_COUNT:
                print(f"{member.id} exceeded join limit ({JOIN_LIMIT_COUNT} in {JOIN_LIMIT_WINDOW_SECONDS}s)")
                oldest = join_history[member.id][0]
                remaining = max(1, int((oldest + timedelta(seconds=JOIN_LIMIT_WINDOW_SECONDS) - now).total_seconds()))
                await send_dm(
                    member,
                    f"You are joining Study Time too frequently. "
                    f"Please wait {format_eta(remaining)} before rejoining to have access to the chat.",
                )
                return

            join_history[member.id].append(now)

            # Check short-stay abuse
            short_stay_history[member.id] = prune_timestamps(
                short_stay_history[member.id], now - timedelta(seconds=SHORT_STAY_WINDOW_SECONDS)
            )
            if len(short_stay_history[member.id]) >= SHORT_STAY_THRESHOLD:
                print(f"{member.id} flagged for short-stay abuse ({len(short_stay_history[member.id])} short visits)")
                oldest = short_stay_history[member.id][0]
                remaining = max(1, int((oldest + timedelta(seconds=SHORT_STAY_WINDOW_SECONDS) - now).total_seconds()))
                await send_dm(
                    member,
                    f"You have been joining Study Time for very short periods too often. "
                    f"Please stay in the channel longer to have access to the chat. "
                    f"Please try again in {format_eta(remaining)}.",
                )
                return

            if target_role not in member.roles:
                await member.add_roles(target_role)

        elif is_left:
            print(f"{member.id} left {old_channel_id} @ {now}")

            # Record short stay if applicable
            join_time = user_joined_at.pop(member.id, None)
            short_stay_duration = (now - join_time).total_seconds() if join_time is not None else None
            if (short_stay_duration is not None) and (short_stay_duration < SHORT_STAY_SECONDS):
                print(f"{member.id} short stay: {short_stay_duration:.0f}s")
                short_stay_history[member.id] = prune_timestamps(
                    short_stay_history[member.id], now - timedelta(seconds=SHORT_STAY_WINDOW_SECONDS)
                )
                short_stay_history[member.id].append(now)

            if target_role in member.roles:
                await member.remove_roles(target_role)
    except Exception as error:
        print(f"An error occurred while processing role change: {error}")

#####

async def main():
  if not discord_token:
    raise RuntimeError("ERROR: DISCORD_TOKEN environment variable is not set!")

  # run the health server FIRST so App Runner health checks pass
  await run_health_server()
  print("Health check server is running on port 8080")
  # Start the Discord bot
  async with bot:
    await bot.start(discord_token)

if __name__ == '__main__':
  asyncio.run(main())
