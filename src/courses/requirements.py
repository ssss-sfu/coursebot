#
import discord

from src.courses.prereqs import number_sort_key
from src.courses.presentation import DESCRIPTION_LIMIT, fit_lines

REQUIREMENT_ORDER = ["W", "Q", "B-Hum", "B-Soc", "B-Sci"]
REQUIREMENT_NAMES = {
  "W": "Writing",
  "Q": "Quantitative",
  "B-Hum": "Breadth-Humanities",
  "B-Soc": "Breadth-Social Sciences",
  "B-Sci": "Breadth-Science",
}
BREADTH_AREAS = {
  "humanities": "B-Hum",
  "hum": "B-Hum",
  "social sciences": "B-Soc",
  "social sci": "B-Soc",
  "soc sci": "B-Soc",
  "soc": "B-Soc",
  "science": "B-Sci",
  "sciences": "B-Sci",
}


def parse_designation(designation: str | None) -> set[str]:
  """SFU's messy designation strings, e.g. "Writing/Breadth-Hum/Soc Sci" or "Q/Breadth-Social Sci/Sciences",
  as a set of W / Q / B-Hum / B-Soc / B-Sci."""
  found: set[str] = set()
  for part in (designation or "").split("/"):
    part = part.strip().removeprefix("Breadth-")
    if part in ("Writing", "W"):
      found.add("W")
    elif part in ("Quantitative", "Q"):
      found.add("Q")
    elif part.lower() in BREADTH_AREAS:
      found.add(BREADTH_AREAS[part.lower()])
  return found


def course_level(number: str) -> int | None:
  """100 for "105W", 300 for "376"; None for numbers like "X91"."""
  return int(number[0]) * 100 if number[:1].isdigit() else None


def filter_courses(
  outlines: list[dict],
  *,
  requirement: str | None = None,
  dept: str | None = None,
  level: int | None = None,
  delivery: str | None = None,
  no_prereqs: bool = False,
  term: str | None = None,
) -> list[dict]:
  """Undergraduate courses matching every filter given, sorted by department and number."""
  matches = []
  for o in outlines:
    if o.get("degreeLevel") != "UGRD":
      continue
    if requirement and requirement not in parse_designation(o.get("designation")):
      continue
    if dept and o.get("dept", "").upper() != dept.strip().upper():
      continue
    if level and course_level(o.get("number", "")) != level:
      continue
    if delivery and o.get("deliveryMethod") != delivery:
      continue
    if no_prereqs and (o.get("prerequisites") or "").strip():
      continue
    if term and not any(t.get("term") == term for t in o.get("offerings", [])):
      continue
    matches.append(o)
  return sorted(matches, key=lambda o: (o.get("dept", ""), number_sort_key(o.get("number", ""))))


def format_course_line(outline: dict) -> str:
  tags = [r for r in REQUIREMENT_ORDER if r in parse_designation(outline.get("designation"))]
  parts = [f"**{outline['dept']} {outline['number']}** {outline.get('title', '')}"]
  if tags:
    parts.append(", ".join(tags))
  if outline.get("deliveryMethod"):
    parts.append(outline["deliveryMethod"])
  return " · ".join(parts)


def build_find_embed(matches: list[dict], filters: list[str]) -> discord.Embed:
  """`filters` are short labels for the title, e.g. ["W", "CMPT", "300-level"]."""
  lines = [format_course_line(o) for o in matches]
  description = fit_lines(lines, DESCRIPTION_LIMIT)
  embed = discord.Embed(
    title=f"Courses: {' · '.join(filters)}"[:256],
    description=description or "No undergraduate courses match those filters.",
    color=discord.Color.blue(),
  )
  if matches:
    shown_all = description == "\n".join(lines)
    count = f"{len(matches)} course{'s' if len(matches) != 1 else ''}"
    embed.set_footer(text=count + ("" if shown_all else " · narrow your filters to see the rest"))
  return embed
