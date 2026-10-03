import re

FIELD_VALUE_LIMIT = 1024
DESCRIPTION_LIMIT = 4096


def parse_term_year(term_code: str) -> int:
  match = re.search(r'(\d{4})', term_code)
  return int(match.group(1)) if match else 0


def format_section_line(section: dict) -> str:
  # the API repeats instructors (once without email, once with); dict.fromkeys dedupes and keeps order
  names = dict.fromkeys(i.get("name") for i in section.get("instructors", []) if i.get("name"))
  # strip(" -") so a schedule with no days/times becomes "" and falls back to TBA instead of showing "-"
  times = [
    f"{s.get('days', '')} {s.get('startTime', '')}-{s.get('endTime', '')}".strip(" -")
    for s in section.get("schedules", [])
  ]
  schedule = "; ".join(t for t in times if t) or "TBA"
  return (
    f"**Section {section.get('section', 'N/A')}** - Instructors: {', '.join(names) or 'TBA'} - Schedule: {schedule}"
  )


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
