import pytest

from src.courses.presentation import FIELD_VALUE_LIMIT, fit_lines, format_section_line, parse_term_year


@pytest.fixture
def cmpt225_sections(load_fixture):
  return load_fixture("sections_cmpt225")[0]["sections"]


def section(**overrides):
  """A section in the real API shape: instructors are {name, email} objects, times live in `schedules`."""
  base = {
    "section": "D100",
    "instructors": [{"name": "Jane Smith", "email": "jsmith@sfu.ca"}],
    "schedules": [{"days": "Mo, We", "startTime": "10:30", "endTime": "11:20"}],
  }
  return {**base, **overrides}


# parse_term_year


@pytest.mark.parametrize(
  ("term", "year"),
  [("2025-fall", 2025), ("fall-2024", 2024), ("Spring 2027", 2027), ("fall-semester", 0), ("", 0)],
)
def test_parse_term_year(term, year):
  assert parse_term_year(term) == year


# format_section_line


def test_real_sections_all_format(cmpt225_sections):
  lines = [format_section_line(s) for s in cmpt225_sections]
  assert len(lines) == len(cmpt225_sections)
  for line, raw in zip(lines, cmpt225_sections, strict=True):
    assert line.startswith(f"**Section {raw['section']}**")
    assert "{" not in line  # no dicts leaking into the text


def test_real_section_shows_instructor_names(cmpt225_sections):
  raw = cmpt225_sections[0]
  line = format_section_line(raw)
  for instructor in raw["instructors"]:
    assert instructor["name"] in line


def test_real_section_shows_schedule_times(cmpt225_sections):
  raw = cmpt225_sections[0]
  first = raw["schedules"][0]
  line = format_section_line(raw)
  assert f"{first['startTime']}-{first['endTime']}" in line
  assert first["days"] in line


def test_duplicate_instructors_listed_once():
  line = format_section_line(
    section(instructors=[{"name": "Amir Aghasharif", "email": ""}, {"name": "Amir Aghasharif", "email": "a@sfu.ca"}])
  )
  assert line.count("Amir Aghasharif") == 1


def test_multiple_instructors_keep_order():
  line = format_section_line(section(instructors=[{"name": "Ada"}, {"name": "Bob"}]))
  assert "Instructors: Ada, Bob" in line


def test_no_instructors_shows_tba():
  assert "Instructors: TBA" in format_section_line(section(instructors=[]))


def test_instructor_without_name_ignored():
  assert "Instructors: TBA" in format_section_line(section(instructors=[{"name": "", "email": "x@sfu.ca"}]))


def test_no_schedules_shows_tba():
  assert format_section_line(section(schedules=[])).endswith("Schedule: TBA")


def test_schedule_without_times_shows_tba():
  assert format_section_line(section(schedules=[{"days": "", "startTime": "", "endTime": ""}])).endswith(
    "Schedule: TBA"
  )


def test_multiple_schedules_joined():
  line = format_section_line(
    section(
      schedules=[
        {"days": "Tu", "startTime": "11:30", "endTime": "13:20"},
        {"days": "Th", "startTime": "14:30", "endTime": "15:20"},
      ]
    )
  )
  assert line.endswith("Schedule: Tu 11:30-13:20; Th 14:30-15:20")


def test_missing_section_code():
  assert format_section_line({"instructors": [], "schedules": []}).startswith("**Section N/A**")


# fit_lines


def test_fit_lines_short_input_unchanged():
  assert fit_lines(["a", "b", "c"], 100) == "a\nb\nc"


def test_fit_lines_exactly_at_limit_unchanged():
  lines = ["x" * 10, "y" * 9]  # 10 + newline + 9 = 20
  assert fit_lines(lines, 20) == "x" * 10 + "\n" + "y" * 9


def test_fit_lines_empty():
  assert fit_lines([], 100) == ""


def test_fit_lines_truncates_with_count():
  lines = [f"line {i:02}" for i in range(100)]
  result = fit_lines(lines, 100)
  assert len(result) <= 100
  kept = result.split("\n")[:-1]
  assert kept == lines[: len(kept)]  # whole lines, in order
  assert result.endswith(f"…and {100 - len(kept)} more")


@pytest.mark.parametrize("limit", [30, 50, 99, 500, FIELD_VALUE_LIMIT])
def test_fit_lines_never_exceeds_limit(limit):
  lines = [f"**Section D{i:03}** - Instructors: Someone Long Named - Schedule: Mo, We 10:30-11:20" for i in range(60)]
  assert len(fit_lines(lines, limit)) <= limit


def test_oversized_real_course_fits_in_a_field(cmpt225_sections):
  sections = cmpt225_sections * 5  # 70 sections: a big course with many labs/tutorials
  result = fit_lines([format_section_line(s) for s in sections], FIELD_VALUE_LIMIT)
  assert len(result) <= FIELD_VALUE_LIMIT
  assert "more" in result.splitlines()[-1]
