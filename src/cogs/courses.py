import re

import discord
from discord import app_commands
from discord.ext import commands

from src.courses import presentation
from src.courses.pagination import send_pages
from src.courses.search import filter_departments, suggest_names
from src.sfu_api import SFUApiError, SFUClient

TERMS = [app_commands.Choice(name=term.title(), value=term) for term in ("spring", "summer", "fall")]


class Courses(commands.Cog):
  def __init__(self, sfu: SFUClient):
    self.sfu = sfu

  async def department_choices(self, current: str) -> list[app_commands.Choice[str]]:
    try:
      departments = await self.sfu.get_departments()
    except SFUApiError as err:
      print(f"department autocomplete failed: {err}")
      return []  # suggestions are optional; the user can still type a code
    return [app_commands.Choice(name=d, value=d) for d in filter_departments(departments, current)]

  # Main Course Command
  # Gets info about a course given subject and course number
  @app_commands.command(name='course', description="Get detailed info about a course")
  @app_commands.describe(subject="Department code, e.g. CMPT", course_number="Course number, e.g. 120 or 105W")
  async def course(self, interaction: discord.Interaction, subject: str, course_number: str):
    await interaction.response.defer()
    raw_number = course_number.strip()
    if not re.fullmatch(r'\d+[A-Za-z]*', raw_number):
      await interaction.followup.send("Invalid course number format. Please use a format like '101' or '105W'.")
      return

    try:
      data = await self.sfu.get_json("/v1/rest/outlines", params={"dept": subject, "number": raw_number})
    except SFUApiError as err:
      print(f"/course failed: {err}")
      await interaction.followup.send("An unexpected error occurred while fetching course outlines.")
      return

    if not data:
      if raw_number == "67":
        await interaction.followup.send("67")
        return
      await interaction.followup.send(f"No course data found for {subject.upper()} {course_number}.")
      return

    course = data[0]
    embed = discord.Embed(
      title=f"{course['dept']} {course['number']}: {course['title']}",
      description=course['description'],
      color=discord.Color.blue(),
    )

    offerings = course.get('offerings', [])
    if offerings:
      sorted_offerings = sorted(offerings, key=lambda x: presentation.parse_term_year(x.get('term', '')), reverse=True)
      offerings_list = []
      for offering in sorted_offerings[:4]:
        term = offering.get('term', 'unknown')
        instructors = offering.get('instructors', [])
        if instructors:
          offerings_list.append(f"• **{term}** - Instructors: {', '.join(instructors)}")
        else:
          offerings_list.append(f"• **{term} - No instructors listed**")
      embed.add_field(name="Recent Offerings", value="\n".join(offerings_list), inline=False)
    else:
      embed.add_field(name="Recent Offerings Found", value="No offerings available", inline=False)
    embed.add_field(name="Credits", value=course['units'], inline=True)
    embed.add_field(name="Prerequisites", value=course['prerequisites'] or "None", inline=True)
    await interaction.followup.send(embed=embed)

  @course.autocomplete("subject")
  async def course_subject_autocomplete(self, interaction: discord.Interaction, current: str):
    return await self.department_choices(current)

  # Instructors Command
  # Returns offerings of courses taught by a specific instructor
  @app_commands.command(name='offerings', description="Get course offerings by instructor")
  @app_commands.describe(
    instructor_name="Instructor's full name, e.g. Brian Fraser", term="Optional term filter, e.g. fall or spring 2026"
  )
  async def offerings(self, interaction: discord.Interaction, instructor_name: str, term: str | None = None):
    await interaction.response.defer()
    try:
      data = await self.sfu.get_json("/v1/rest/instructors", params={"name": instructor_name})
    except SFUApiError as err:
      print(f"/offerings failed: {err}")
      embed = discord.Embed(
        title="Server Error",
        description="Couldn't reach the SFU Courses API. Try again later.",
        color=discord.Color.red(),
      )
      await interaction.followup.send(embed=embed)
      return

    if not data:  # None (404) or [] (no match)
      embed = discord.Embed(
        title="No Instructors Found",
        description=f"No instructors found with the name '{instructor_name}'",
        color=discord.Color.red(),
      )
      embed.set_footer(text="Tip: Check your spelling or try using instructor's full name.")
      await interaction.followup.send(embed=embed)
      return

    if len(data) > 1:
      instructor_list = "\n".join(f"• {instructor.get('name', 'Unknown')}" for instructor in data[:10])
      embed = discord.Embed(
        title="Multiple Instructors Found",
        description=f"Found {len(data)} instructors matching your search:",
        color=discord.Color.orange(),
      )
      embed.add_field(name="Matching Instructors:", value=instructor_list, inline=False)
      embed.set_footer(text="Tip: Retry /offerings with the instructor's full name.")
      await interaction.followup.send(embed=embed)
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
        await interaction.followup.send(embed=embed)
        return

    if not offerings:
      embed = discord.Embed(
        title=f"Courses taught by {name}", description="No offerings found.", color=discord.Color.green()
      )
      await interaction.followup.send(embed=embed)
      return

    await send_pages(interaction, presentation.build_offerings_pages(name, offerings))

  # Section Command
  # Returns section info for a specific course in a specific year and term
  @app_commands.command(name='section', description="Get course sections for a specific year and term")
  @app_commands.describe(year="Year, e.g. 2026", term="Term", dept="Department code, e.g. CMPT", number="Course number")
  @app_commands.choices(term=TERMS)
  async def section(
    self,
    interaction: discord.Interaction,
    year: app_commands.Range[int, 2000, 2100],
    term: app_commands.Choice[str],
    dept: str,
    number: str,
  ):
    await interaction.response.defer()
    term = term.value
    try:
      data = await self.sfu.get_json(
        "/v1/rest/sections", params={"term": f"{year}-{term}", "dept": dept, "number": number}
      )
    except SFUApiError as err:
      print(f"/section failed: {err}")
      embed = discord.Embed(
        title="Server Error", description="Internal Server Error from not this bot lol", color=discord.Color.red()
      )
      await interaction.followup.send(embed=embed)
      return

    if not data:
      embed = discord.Embed(
        title="No Sections Found",
        description=f"No sections found for {dept} {number} in {year}-{term}",
        color=discord.Color.red(),
      )
      await interaction.followup.send(embed=embed)
      return

    course = data[0]
    embed = discord.Embed(
      title=f"{course['dept']} {course['number']}: {course['title']} ({year}-{term})",
      description=f"Units: {course['units']}",
      color=discord.Color.green(),
    )
    sections = course.get('sections', [])
    if sections:
      lines = [presentation.format_section_line(s) for s in sections]
      embed.add_field(
        name="Sections:", value=presentation.fit_lines(lines, presentation.FIELD_VALUE_LIMIT), inline=False
      )
    else:
      embed.add_field(name="Sections:", value="No sections available", inline=False)
    await interaction.followup.send(embed=embed)

  @section.autocomplete("dept")
  async def section_dept_autocomplete(self, interaction: discord.Interaction, current: str):
    return await self.department_choices(current)

  # Reviews Command
  # Returns a summary of review data for specified Instructor
  @app_commands.command(name='reviews', description="Get reviews for a specific instructor")
  @app_commands.describe(instructor_name="Instructor's full name, e.g. Brian Fraser")
  async def reviews(self, interaction: discord.Interaction, instructor_name: str):
    await interaction.response.defer()
    try:
      data = await self.sfu.get_instructor_reviews()
    except SFUApiError as err:
      print(f"/reviews failed: {err}")
      embed = discord.Embed(
        title="Error", description="Failed to fetch reviews. Try again later.", color=discord.Color.red()
      )
      await interaction.followup.send(embed=embed)
      return

    if not data:
      embed = discord.Embed(
        title="No Data Available",
        description="Could not retrieve instructor reviews at this time.",
        color=discord.Color.red(),
      )
      await interaction.followup.send(embed=embed)
      return

    query = instructor_name.strip().lower()
    matches = [s for s in data if s.get('Name', '').strip().lower() == query]
    if not matches:
      embed = discord.Embed(
        title="No Reviews Found", description=f"No reviews found for '{instructor_name}'.", color=discord.Color.red()
      )
      suggestions = suggest_names(instructor_name, [s.get('Name', '') for s in data])
      if suggestions:
        embed.add_field(name="Did you mean?", value="\n".join(f"• {s}" for s in suggestions), inline=False)
      embed.set_footer(text="Tip: Check spelling or try the instructor's full name.")
      await interaction.followup.send(embed=embed)
      return

    if len(matches) > 1:
      # different professors share this name (usually in different departments): show each one
      embed = discord.Embed(
        title=f"{len(matches)} professors named {matches[0].get('Name', instructor_name)}",
        color=discord.Color.purple(),
      )
      for prof in matches[:25]:
        url = prof.get('URL', '')
        embed.add_field(
          name=prof.get('Department', 'Unknown department'),
          value=format_rating(prof) + (f"\n[RateMyProfessors]({url})" if url else ""),
          inline=False,
        )
      await interaction.followup.send(embed=embed)
      return

    found_prof = matches[0]
    url = found_prof.get('URL', '')
    embed = discord.Embed(
      title=f"Reviews for {found_prof.get('Name', instructor_name)}",
      description=f"Professor in the **{found_prof.get('Department', 'Unknown')}** department at SFU.",
      url=url or None,
      color=discord.Color.purple(),
    )
    embed.add_field(name="Information", value=format_rating(found_prof), inline=False)
    await interaction.followup.send(embed=embed)


def format_rating(prof: dict) -> str:
  return (
    f"• Rating: {prof.get('Quality', 'N/A')}/5\n"
    f"• Difficulty: {prof.get('Difficulty', 'N/A')}/5\n"
    f"• Ratings: {prof.get('Ratings', 'N/A')}\n"
    f"• {prof.get('WouldTakeAgain', 'N/A')} of students Would Take Again"
  )
