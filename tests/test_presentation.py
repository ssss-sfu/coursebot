from datetime import date

import pytest

from src.courses.presentation import (
  FIELD_VALUE_LIMIT,
  build_offerings_pages,
  current_and_next_term,
  fit_lines,
  group_offerings_by_year,
  parse_term_year,
  term_sort_key,
)

# parse_term_year


@pytest.mark.parametrize(
  ("term", "year"),
  [("2025-fall", 2025), ("Spring 2027", 2027), ("fall-semester", 0)],
)
def test_parse_term_year(term, year):
  assert parse_term_year(term) == year


# fit_lines


def test_fit_lines_exactly_at_limit_unchanged():
  lines = ["x" * 10, "y" * 9]  # 10 + newline + 9 = 20
  assert fit_lines(lines, 20) == "x" * 10 + "\n" + "y" * 9


def test_fit_lines_truncates_with_count():
  lines = [f"line {i:02}" for i in range(100)]
  result = fit_lines(lines, 100)
  assert len(result) <= 100
  kept = result.split("\n")[:-1]
  assert kept == lines[: len(kept)]  # whole lines, in order
  assert result.endswith(f"…and {100 - len(kept)} more")


@pytest.mark.parametrize("limit", [50, FIELD_VALUE_LIMIT])
def test_fit_lines_never_exceeds_limit(limit):
  lines = [f"**Section D{i:03}** - Instructors: Someone Long Named - Schedule: Mo, We 10:30-11:20" for i in range(60)]
  assert len(fit_lines(lines, limit)) <= limit


# offerings grouped by year


def offering(term, number="120"):
  return {"dept": "CMPT", "number": number, "title": "Intro", "term": term}


@pytest.mark.parametrize(
  ("term", "key"),
  [("Fall 2026", (2026, 3)), ("spring 2026", (2026, 1)), ("", (0, 0))],
)
def test_term_sort_key(term, key):
  assert term_sort_key(term) == key


@pytest.mark.parametrize(
  ("today", "terms"),
  [
    (date(2026, 4, 30), ["Spring 2026", "Summer 2026"]),
    (date(2026, 5, 1), ["Summer 2026", "Fall 2026"]),
    (date(2026, 12, 31), ["Fall 2026", "Spring 2027"]),
  ],
)
def test_current_and_next_term(today, terms):
  assert current_and_next_term(today) == terms


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


def test_build_offerings_pages_titles_and_footers():
  pages = build_offerings_pages("Jane Smith", [offering("Fall 2026"), offering("TBA", number="999")])
  assert [p.title for p in pages] == ["Courses taught by Jane Smith · 2026", "Courses taught by Jane Smith · Other"]
  assert [p.footer.text for p in pages] == ["Page 1/2 · 2026", "Page 2/2 · Other"]
  assert pages[0].description == "**CMPT 120** - Intro (Fall 2026)"
