import pytest

from src.courses.presentation import (
  DESCRIPTION_LIMIT,
  FIELD_VALUE_LIMIT,
  build_offerings_pages,
  fit_lines,
  format_section_line,
  group_offerings_by_year,
  parse_term_year,
  term_sort_key,
)


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


# offerings grouped by year


def offering(term, number="120"):
  return {"dept": "CMPT", "number": number, "title": "Intro", "term": term}


@pytest.mark.parametrize(
  ("term", "key"),
  [("Fall 2026", (2026, 3)), ("Summer 2026", (2026, 2)), ("spring 2026", (2026, 1)), ("2026", (2026, 0)), ("", (0, 0))],
)
def test_term_sort_key(term, key):
  assert term_sort_key(term) == key


def test_groups_newest_year_first_and_skips_missing_years():
  groups = group_offerings_by_year([offering("Spring 2024"), offering("Fall 2027"), offering("Fall 2024")])
  assert [year for year, _ in groups] == [2027, 2024]


def test_terms_within_a_year_newest_first():
  [(_, year_offerings)] = group_offerings_by_year(
    [offering("Spring 2026"), offering("Fall 2026"), offering("Summer 2026")]
  )
  assert [o["term"] for o in year_offerings] == ["Fall 2026", "Summer 2026", "Spring 2026"]


def test_offerings_without_a_year_go_last():
  groups = group_offerings_by_year([offering("TBA"), offering("Fall 2025")])
  assert [year for year, _ in groups] == [2025, 0]


def test_real_fraser_offerings_grouped(load_fixture):
  offerings = load_fixture("instructors_fraser")[0]["offerings"]
  groups = group_offerings_by_year(offerings)
  assert sum(len(g) for _, g in groups) == len(offerings)
  assert [y for y, _ in groups] == sorted({parse_term_year(o["term"]) for o in offerings}, reverse=True)


def test_build_offerings_pages_titles_and_footers():
  pages = build_offerings_pages("Jane Smith", [offering("Fall 2026"), offering("TBA", number="999")])
  assert [p.title for p in pages] == ["Courses taught by Jane Smith · 2026", "Courses taught by Jane Smith · Other"]
  assert [p.footer.text for p in pages] == ["Page 1/2 · 2026", "Page 2/2 · Other"]
  assert pages[0].description == "**CMPT 120** - Intro (Fall 2026)"


def test_single_year_page_has_no_footer():
  [page] = build_offerings_pages("Jane Smith", [offering("Fall 2026")])
  assert page.footer.text is None


def test_huge_year_still_fits_description_limit():
  [page] = build_offerings_pages("Jane Smith", [offering("Fall 2026", number=str(i)) for i in range(500)])
  assert len(page.description) <= DESCRIPTION_LIMIT
