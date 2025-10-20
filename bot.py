from dotenv import load_dotenv
import discord
from discord.ext import commands
from typing import Optional
import os

load_dotenv()  # Load environment variables from .env file
discord_token = os.getenv('DISCORD_TOKEN')

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

bot.run(discord_token)