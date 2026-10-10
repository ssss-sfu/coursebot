# purpose of this file is shared formatting.
import re
from datetime import date

import discord

# discord embeds have size limits:
FIELD_VALUE_LIMIT = 1024
DESCRIPTION_LIMIT = 4096


# sorts years
def parse_term_year(term_code: str) -> int:
  match = re.search(r'(\d{4})', term_code)
  return int(match.group(1)) if match else 0


# Keeps as many whole lines as can fit, then adds a generic message
def fit_lines(lines: list[str], limit: int) -> str:
  """Join whole lines up to `limit` characters, ending with "…and N more" when some don't fit."""
  text = "\n".join(lines)
  if len(text) <= limit:
    return text
  kept: list[str] = []
  for i, line in enumerate(lines):
    remaining_after = len(lines) - i - 1
    if len("\n".join([*kept, line])) + len(f"\n…and {remaining_after} more") > limit:
      break
    kept.append(line)
  return "\n".join([*kept, f"…and {len(lines) - len(kept)} more"])


SEASON_ORDER = {"spring": 1, "summer": 2, "fall": 3}


# sorts terms/ seasons
def term_sort_key(term: str) -> tuple[int, int]:
  """(year, season) so terms sort chronologically; unknown parts sort as 0."""
  season = next((rank for name, rank in SEASON_ORDER.items() if name in term.lower()), 0)
  return parse_term_year(term), season


def current_and_next_term(today: date) -> list[str]:
  """SFU terms: Spring = Jan–Apr, Summer = May–Aug, Fall = Sep–Dec."""
  if today.month <= 4:
    return [f"Spring {today.year}", f"Summer {today.year}"]
  if today.month <= 8:
    return [f"Summer {today.year}", f"Fall {today.year}"]
  return [f"Fall {today.year}", f"Spring {today.year + 1}"]


# Year paging
def group_offerings_by_year(offerings: list[dict]) -> list[tuple[int, list[dict]]]:
  """[(year, offerings)] newest year first, newest term first within a year; only years that have offerings.
  Offerings whose term has no year are grouped under 0, which sorts last."""
  ordered = sorted(offerings, key=lambda o: term_sort_key(o.get('term', '')), reverse=True)
  groups: dict[int, list[dict]] = {}
  for offering in ordered:
    groups.setdefault(parse_term_year(offering.get('term', '')), []).append(offering)
  years = sorted((y for y in groups if y), reverse=True) + ([0] if 0 in groups else [])
  return [(year, groups[year]) for year in years]


def format_offering_line(offering: dict) -> str:
  return (
    f"**{offering.get('dept', 'N/A')} {offering.get('number', 'N/A')}** - "
    f"{offering.get('title', 'N/A')} ({offering.get('term', 'N/A')})"
  )


def build_offerings_pages(name: str, offerings: list[dict]) -> list[discord.Embed]:
  """One embed per year the instructor taught, newest first."""
  groups = group_offerings_by_year(offerings)
  pages = []
  for page_number, (year, year_offerings) in enumerate(groups, start=1):
    embed = discord.Embed(
      title=f"Courses taught by {name} · {year or 'Other'}",
      description=fit_lines([format_offering_line(o) for o in year_offerings], DESCRIPTION_LIMIT),
      color=discord.Color.green(),
    )
    if len(groups) > 1:
      embed.set_footer(text=f"Page {page_number}/{len(groups)} · {year or 'Other'}")
    pages.append(embed)
  return pages
