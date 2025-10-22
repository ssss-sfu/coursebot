from dotenv import load_dotenv
import discord
from discord.ext import commands
from typing import Optional
import os  # HTTP client for making API requests
import http.client
import json
import re

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

@bot.hybrid_command(name='courseinfo2', with_app_command=True, description="Get detailed info about a course")
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
            await ctx.send(f"This course does not exist. Please try again.")
            return
        data = json.loads(outlines.decode('utf-8'))
        if not data:
            await ctx.send("No course data found.")
        course = data[0]
        embed = discord.Embed(
            title=f"{course['dept']} {course['number']}: {course['title']}",
            description = course['description'],
            color=discord.Color.blue()
        )
        embed.add_field(name="Credits", value=course['units'], inline=True)
        embed.add_field(name="Prerequisites", value=course['prerequisites'] or "None", inline=True)
        await ctx.send(embed=embed)
    elif response.status == 404:
        await ctx.send(f"Error fetching course outlines: {response.status}")
    else:
        await ctx.send()
    

bot.run(discord_token)