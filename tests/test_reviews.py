from datetime import date

import pytest

from src.courses.reviews import (
  MIN_RETAKE_ANSWERS,
  MIN_REVIEWS_TO_RANK,
  TOP_COUNT,
  TOP_COUNT_WHEN_MANY_TEACHING,
  build_course_reviews_embed,
  current_and_next_term,
  format_instructor_line,
  rank_instructors,
  select_lines,
  teaching_terms,
  would_take_again_percent,
)


@pytest.fixture
def cmpt225_reviews(load_fixture):
  return load_fixture("course_reviews_cmpt225")


@pytest.fixture
def cmpt225_outline(load_fixture):
  return load_fixture("outlines_cmpt225")[0]


def instructor(name="Jane Smith", rating=4.0, difficulty=3.0, count=10, professor_id="123", answers=()):
  return {
    "professor_id": professor_id,
    "professor_name": name,
    "avg_rating": rating,
    "avg_difficulty": difficulty,
    "review_count": count,
    "would_take_again": "",
    "reviews": [{"metadata": {"Would Take Again": a}} for a in answers],
  }


# current_and_next_term


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


# teaching_terms


def test_teaching_terms_in_term_order_and_name_kept():
  offerings = [
    {"term": "Spring 2027", "instructors": ["Victor Cheung", "Keval Vora"]},
    {"term": "Fall 2026", "instructors": ["Igor Shinkar", "Victor Cheung"]},
    {"term": "Fall 2025", "instructors": ["Old Prof"]},
  ]
  teaching = teaching_terms(offerings, ["Fall 2026", "Spring 2027"])
  assert teaching["victor cheung"] == ("Victor Cheung", ["Fall 2026", "Spring 2027"])
  assert teaching["keval vora"] == ("Keval Vora", ["Spring 2027"])
  assert "old prof" not in teaching


# would_take_again_percent


def test_would_take_again_percent_ignores_blank_answers():
  assert (
    would_take_again_percent([{"metadata": {"Would Take Again": a}} for a in ["Yes"] * 3 + ["No"] * 2 + [""] * 10])
    == 60
  )


def test_would_take_again_hidden_below_minimum_answers():
  answers = ["Yes"] * (MIN_RETAKE_ANSWERS - 1) + [""] * 20
  assert would_take_again_percent([{"metadata": {"Would Take Again": a}} for a in answers]) is None


# rank_instructors


def test_rank_by_rating_then_review_count():
  ranked, _ = rank_instructors(
    [instructor("A", rating=4.0, count=5), instructor("B", rating=4.5, count=4), instructor("C", rating=4.0, count=50)]
  )
  assert [i["professor_name"] for i in ranked] == ["B", "C", "A"]


def test_few_reviews_ranked_separately():
  ranked, few = rank_instructors(
    [instructor("Lots", rating=3.0, count=MIN_REVIEWS_TO_RANK), instructor("Two", rating=5.0, count=2)]
  )
  assert [i["professor_name"] for i in ranked] == ["Lots"]
  assert [i["professor_name"] for i in few] == ["Two"]


# format_instructor_line


def test_line_links_name_and_shows_stats():
  line = format_instructor_line(
    instructor(
      "Brian Fraser", rating=4.4, difficulty=3.1, count=85, professor_id="1442290", answers=["Yes"] * 9 + ["No"]
    ),
    {},
  )
  assert line == (
    "[Brian Fraser](https://www.ratemyprofessors.com/professor/1442290)"
    " · 4.4/5 · difficulty 3.1 · 85 reviews · 90% would retake"
  )


# select_lines


def teaching_for(*names, term="Fall 2026"):
  return {" ".join(n.lower().split()): (n, [term]) for n in names}


def names(lines):
  return [line.split("](")[0].lstrip("[").split(" · ")[0] for line in lines]


def test_nobody_teaching_shows_top_three_by_rating():
  instructors = [instructor(f"P{i}", rating=r) for i, r in enumerate([3.0, 4.5, 2.0, 4.0, 5.0])]
  assert names(select_lines(instructors, {})) == ["P4", "P1", "P3"]


def test_teaching_soon_goes_first_even_if_rated_lower():
  instructors = [instructor("Best", rating=5.0), instructor("Good", rating=4.5), instructor("Teaching", rating=2.0)]
  assert names(select_lines(instructors, teaching_for("Teaching"))) == ["Teaching", "Best", "Good"]


def test_teaching_soon_without_reviews_listed_after_reviewed_teachers():
  lines = select_lines(
    [instructor("Rated", rating=4.0), instructor("Other", rating=5.0)], teaching_for("Rated", "New Prof")
  )
  assert lines[0].startswith("[Rated](")
  assert lines[1] == "New Prof · no reviews yet (teaching Fall 2026)"
  assert lines[2].startswith("[Other](")


def test_three_teaching_still_shows_three():
  instructors = [instructor(n, rating=4.0) for n in ["A", "B", "C", "D"]]
  lines = select_lines(instructors, teaching_for("A", "B", "C"))
  assert len(lines) == TOP_COUNT
  assert names(lines) == ["A", "B", "C"]


def test_more_than_three_teaching_shows_five():
  instructors = [instructor(n, rating=4.0) for n in ["A", "B", "C", "D", "E", "F"]]
  lines = select_lines(instructors, teaching_for("A", "B", "C", "D"))
  assert len(lines) == TOP_COUNT_WHEN_MANY_TEACHING
  assert names(lines)[:4] == ["A", "B", "C", "D"]


# build_course_reviews_embed (real CMPT 225 data, as of Fall 2026: Shinkar + Baig in Fall, Cheung + Vora in Spring)


def test_real_embed_title_and_footer(cmpt225_reviews, cmpt225_outline):
  embed = build_course_reviews_embed("cmpt", "225", cmpt225_reviews, cmpt225_outline, date(2026, 10, 4))
  assert embed.title == f"CMPT 225: Data Structures and Programming — {cmpt225_reviews['total_reviews']} reviews"
  assert (
    embed.footer.text == f"Top 5 of {len(cmpt225_reviews['instructors'])} instructors · ratings from RateMyProfessors"
  )


def test_real_embed_teaching_first_then_top_rated(cmpt225_reviews, cmpt225_outline):
  embed = build_course_reviews_embed("CMPT", "225", cmpt225_reviews, cmpt225_outline, date(2026, 10, 4))
  lines = embed.description.splitlines()
  assert len(lines) == 5  # four people teach Fall 2026 / Spring 2027
  assert lines[0].startswith("[Igor Shinkar](") and lines[0].endswith("(teaching Fall 2026)")
  assert lines[1].startswith("[Victor Cheung](") and lines[1].endswith("(teaching Spring 2027)")
  assert lines[2] == "Mirza Zaeem Baig · no reviews yet (teaching Fall 2026)"
  assert lines[3] == "Keval Vora · no reviews yet (teaching Spring 2027)"
  assert lines[4].startswith("[Jocelyn Minns](")


def test_embed_without_outline_uses_course_code(cmpt225_reviews):
  embed = build_course_reviews_embed("cmpt", "225", cmpt225_reviews, None, date(2026, 10, 4))
  assert embed.title.startswith("CMPT 225 — ")
  assert len(embed.description.splitlines()) == TOP_COUNT
