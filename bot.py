from dotenv import load_dotenv
import discord
from discord.ext import commands
from typing import Optional
import os  # HTTP client for making API requests
import http.client

load_dotenv()  # Load environment variables from .env file
discord_token = os.getenv('DISCORD_TOKEN')
conn = http.client.HTTPSConnection("api.sfucourses.com")

# Creates an instance of a client. This is our conneciton to discord.
intents = discord.Intents.default() 
intents.message_content = True # Enable message content intent
# Registers an event. This event is called when the bot has switched from offline to online.
bot = commands.Bot(command_prefix='!', intents=intents, case_insensitive=True) # command handling

@bot.event
async def on_ready():
    print(f'Bot is online as {bot.user}')
    # Sync slash commands to Discord
    synched = await bot.tree.sync()
    print(f"Synced {len(synched)} command(s)")

# Main Course Command
# Gets info about a course given subject and course number
# Can give optioanl arguments for Semester, Section, Instructor Userid, and Campus
# TODO: Create a list of enums for parameters(subject, course number, semester, section, instructor_userid, campus)
#       or check the course API to see what parameters are accepted
# need to validate entered parameters... if the course doesnt exist, return an error message etc.
@bot.hybrid_command(name='course', with_app_command=True, description="Get info about a course")
async def course(ctx: commands.Context, subject: str, course_number: int, semester: str = "Spring 2025", section: Optional[str] = None, instructor_userid: Optional[str] = None, campus: Optional[str] = None):
    await ctx.send(f"ok you want info for {subject}{course_number} for {semester}... working on it rn")

@bot.hybrid_command(name='courseinfo', with_app_command=True, description="Get detailed info about a course")
async def get_outlines(ctx: commands.Context, subject: str, course_number: int):
    # Placeholder implementation
    # use http.client to fetch detailed course info from the API
    conn.request("GET", f"/v1/rest/outlines?dept={subject}&number={course_number}")
    response = conn.getresponse()
    if response.status == 200:
        outlines = response.read()
        await ctx.send(f"Course outlines for {subject}{course_number}: {outlines}")
    else:
        await ctx.send(f"Error fetching course outlines: {response.status}")

bot.run(discord_token)