from dotenv import load_dotenv
import discord
from discord.ext import commands
from typing import Optional
import os 
import http.client
import json
import re
import urllib.parse
# health check imports
import asyncio
from aiohttp import web

# helper function to parse term year
def parse_term_year(term_code: str):
    match = re.search(r'(\d{4})', term_code)
    return int(match.group(1)) if match else 0

#helper function to check the command type
def get_command_type(ctx: commands.Context) -> str:
    return 'slash' if ctx.interaction else 'prefix'

load_dotenv()  # Load environment variables from .env file
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
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()


@bot.event
async def on_ready():
    print(f'Bot is online as {bot.user}')
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} command(s)")
    print("Available commands:", [cmd.name for cmd in synced])

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
                    offerings_list.append(f"**{term}** - Instructors: {instructor_str}")
                else:
                    offerings_list.append(f"**{term} - No instructors listed**")
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
        await ctx.send()

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

async def main():
    # run the health server
    await run_health_server()
    print("Health check server is running on port 8080")
    # wait a moment for the server to start
    await asyncio.sleep(2)
    async with bot:
        await bot.start(discord_token)

if __name__ == '__main__':
    asyncio.run(main())