# unlocks helper file
import re
from collections import defaultdict

import discord

from src.courses.presentation import DESCRIPTION_LIMIT, fit_lines

# A department code, a 3-digit course number (optionally with a letter, e.g. 272W), or a sentence break.
# Numbers followed by "-level", "-division" or "units" describe requirements, not courses.
TOKEN = re.compile(
  r"(?P<dept>\b[A-Z]{2,4}\b)"
  r"|(?P<number>\b\d{3}[A-Z]?\b)(?!\s*-|\s+(?:units?|credits?|hours?)\b)"
  r"|(?P<stop>[.;])"
)
COREQUISITE = re.compile(r"co-?requisite", re.IGNORECASE)


def course_key(dept: str, number: str) -> tuple[str, str]:
  return dept.strip().upper(), number.strip().upper()


def prerequisite_codes(text: str | None, departments: set[str]) -> list[tuple[str, str]]:
  """Course codes mentioned in free-text prerequisites, in order. Bare numbers continue the last department
  ("ARCH 100, 101, or 201"); codes that aren't current departments are skipped ("CA (or FPA) 122") or, when
  followed by a number ("HS 231"), stop the carry-over; anything after
  "Corequisite" is skipped."""
  text = COREQUISITE.split(text or "", maxsplit=1)[0]
  codes: list[tuple[str, str]] = []
  last_dept = None
  for match in TOKEN.finditer(text):
    if match.group("stop"):
      last_dept = None
    elif match.group("dept"):
      if match.group("dept") in departments:
        last_dept = match.group("dept")
      elif re.match(r"\s+\d", text[match.end() :]):
        last_dept = None  # e.g. "HS 231": the number belongs to a department we don't know, not the previous one
    elif last_dept:
      code = (last_dept, match.group("number"))
      if code not in codes:
        codes.append(code)
  return codes


def build_unlocks_index(outlines: list[dict]) -> dict[tuple[str, str], list[dict]]:
  """{(dept, number): [outlines whose prerequisites mention it]}"""
  departments = {o["dept"] for o in outlines if o.get("dept")}
  index: dict[tuple[str, str], list[dict]] = defaultdict(list)
  for outline in outlines:
    own = course_key(outline.get("dept", ""), outline.get("number", ""))
    for code in prerequisite_codes(outline.get("prerequisites"), departments):
      if code != own:
        index[code].append(outline)
  return index


def find_outline(outlines: list[dict], dept: str, number: str) -> dict | None:
  target = course_key(dept, number)
  return next((o for o in outlines if course_key(o.get("dept", ""), o.get("number", "")) == target), None)


def number_sort_key(number: str) -> tuple[int, str]:
  digits = re.match(r"\d+", number)
  return (int(digits.group()) if digits else 10**6, number)


def build_unlocks_embed(course: dict, unlocked: list[dict]) -> discord.Embed:
  """One message listing `unlocked` grouped by department, the course's own department first."""
  dept, number = course_key(course.get("dept", ""), course.get("number", ""))
  code = f"{dept} {number}"
  by_dept: dict[str, list[dict]] = defaultdict(list)
  for outline in unlocked:
    by_dept[outline["dept"]].append(outline)

  lines: list[str] = []
  for group in sorted(by_dept, key=lambda d: (d != dept, d)):
    lines.append(f"**{group}**")
    for outline in sorted(by_dept[group], key=lambda o: number_sort_key(o.get("number", ""))):
      lines.append(f"{outline['dept']} {outline['number']} · {outline.get('title', '')}")

  embed = discord.Embed(
    title=f"What {code} unlocks",
    description=fit_lines(lines, DESCRIPTION_LIMIT) if lines else f"No courses list {code} as a prerequisite.",
    color=discord.Color.teal(),
  )
  if lines:
    embed.set_footer(
      text=f"{len(unlocked)} courses mention {code} in their prerequisites · based on prerequisite text; "
      "check the SFU calendar"
    )
  return embed
