# course-reviews helper
from datetime import date

import discord

from src.courses.presentation import DESCRIPTION_LIMIT, fit_lines

MIN_REVIEWS_TO_RANK = 3
TOP_COUNT = 3
TOP_COUNT_WHEN_MANY_TEACHING = 5  # used when more than TOP_COUNT people teach the current/next term
MIN_RETAKE_ANSWERS = 5  # most reviews leave "Would Take Again" blank; 2 answers shouldn't read as "100%"
RMP_PROFESSOR_URL = "https://www.ratemyprofessors.com/professor/{}"


# Finds the current and next terms from today's date and whos teaching them
def current_and_next_term(today: date) -> list[str]:
  """SFU terms: Spring = Jan–Apr, Summer = May–Aug, Fall = Sep–Dec."""
  if today.month <= 4:
    return [f"Spring {today.year}", f"Summer {today.year}"]
  if today.month <= 8:
    return [f"Summer {today.year}", f"Fall {today.year}"]
  return [f"Fall {today.year}", f"Spring {today.year + 1}"]


def name_key(name: str) -> str:
  return " ".join(name.lower().split())


def teaching_terms(offerings: list[dict], terms: list[str]) -> dict[str, tuple[str, list[str]]]:
  """{normalized name: (name as written, [terms they teach])} for the given terms, in the order of `terms`."""
  teaching: dict[str, tuple[str, list[str]]] = {}
  for term in terms:
    for offering in offerings:
      if offering.get("term") == term:
        for name in offering.get("instructors", []):
          entry = teaching.setdefault(name_key(name), (name.strip(), []))
          if term not in entry[1]:
            entry[1].append(term)
  return teaching


def would_take_again_percent(reviews: list[dict]) -> int | None:
  """% of "Yes" among reviews that answered Yes or No; None if fewer than MIN_RETAKE_ANSWERS answered."""
  answers = [r.get("metadata", {}).get("Would Take Again", "") for r in reviews]
  yes, no = answers.count("Yes"), answers.count("No")
  if yes + no < MIN_RETAKE_ANSWERS:
    return None
  return round(100 * yes / (yes + no))


# ranks instructors based on their reviews
def rank_instructors(instructors: list[dict]) -> tuple[list[dict], list[dict]]:
  """(ranked, few_reviews): best rating first, more reviews winning ties; instructors with
  fewer than MIN_REVIEWS_TO_RANK reviews are ranked separately so a couple of reviews can't top the list."""

  def key(i: dict):
    return (-float(i.get("avg_rating") or 0), -int(i.get("review_count") or 0), name_key(i.get("professor_name", "")))

  ranked = sorted((i for i in instructors if (i.get("review_count") or 0) >= MIN_REVIEWS_TO_RANK), key=key)
  few = sorted((i for i in instructors if 0 < (i.get("review_count") or 0) < MIN_REVIEWS_TO_RANK), key=key)
  return ranked, few


def format_instructor_line(instructor: dict, teaching: dict[str, tuple[str, list[str]]]) -> str:
  name = instructor.get("professor_name", "Unknown")
  professor_id = instructor.get("professor_id")
  linked = f"[{name}]({RMP_PROFESSOR_URL.format(professor_id)})" if professor_id else name
  count = instructor.get("review_count") or 0
  parts = [
    linked,
    f"{float(instructor.get('avg_rating') or 0):.1f}/5",
    f"difficulty {float(instructor.get('avg_difficulty') or 0):.1f}",
    f"{count} review{'s' if count != 1 else ''}",
  ]
  percent = would_take_again_percent(instructor.get("reviews", []))
  if percent is not None:
    parts.append(f"{percent}% would retake")
  line = " · ".join(parts)
  if name_key(name) in teaching:
    line += f" (teaching {', '.join(teaching[name_key(name)][1])})"
  return line


def select_lines(instructors: list[dict], teaching: dict[str, tuple[str, list[str]]]) -> list[str]:
  """Instructors teaching the current/next term first (reviewed by rank, then unreviewed), then the best-rated
  others; TOP_COUNT lines, or TOP_COUNT_WHEN_MANY_TEACHING when more than TOP_COUNT people are teaching."""
  ranked, few = rank_instructors(instructors)
  ordered = ranked + few
  reviewed_keys = {name_key(i.get("professor_name", "")) for i in ordered}

  lines = [format_instructor_line(i, teaching) for i in ordered if name_key(i.get("professor_name", "")) in teaching]
  lines += [
    f"{name} · no reviews yet (teaching {', '.join(terms)})"
    for key, (name, terms) in teaching.items()
    if key not in reviewed_keys
  ]
  lines += [
    format_instructor_line(i, teaching) for i in ordered if name_key(i.get("professor_name", "")) not in teaching
  ]

  limit = TOP_COUNT_WHEN_MANY_TEACHING if len(teaching) > TOP_COUNT else TOP_COUNT
  return lines[:limit]


def build_course_reviews_embed(
  dept: str, number: str, reviews: dict, outline: dict | None, today: date
) -> discord.Embed:
  """`reviews` is the /reviews/courses/{code} response; `outline` (for the title and who's teaching) may be None."""
  code = f"{dept.upper()} {number.upper()}"
  title = f"{code}: {outline['title']}" if outline and outline.get("title") else code
  teaching = teaching_terms((outline or {}).get("offerings", []), current_and_next_term(today))
  instructors = reviews.get("instructors", [])
  lines = select_lines(instructors, teaching)

  embed = discord.Embed(
    title=f"{title} — {reviews.get('total_reviews', 0)} reviews",
    description=fit_lines(lines, DESCRIPTION_LIMIT),
    color=discord.Color.purple(),
  )
  embed.set_footer(text=f"Top {len(lines)} of {len(instructors)} instructors · ratings from RateMyProfessors")
  return embed
