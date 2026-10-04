import pytest

from src.courses.prereqs import build_unlocks_embed, build_unlocks_index, find_outline, prerequisite_codes

DEPARTMENTS = {"ARCH", "CA", "CMPT", "EASC", "ENSC", "HIST", "MACM", "MATH", "PHYS", "STAT", "BPK"}


@pytest.fixture
def samples(load_fixture):
  return load_fixture("outlines_prereq_samples")


# prerequisite_codes (strings copied from real outlines)


@pytest.mark.parametrize(
  ("text", "codes"),
  [
    ("ARCH 100, 101, or 201.", [("ARCH", "100"), ("ARCH", "101"), ("ARCH", "201")]),  # department carried forward
    ("ARCH 272W or 273 or by permission of instructor.", [("ARCH", "272W"), ("ARCH", "273")]),
    (
      "(MACM 101 and (CMPT 125, CMPT 129 or CMPT 135)) or (ENSC 251 and ENSC 252)",
      [("MACM", "101"), ("CMPT", "125"), ("CMPT", "129"), ("CMPT", "135"), ("ENSC", "251"), ("ENSC", "252")],
    ),
    (
      "BPK 142, 143 and 205; STAT 201 or an equivalent",
      [("BPK", "142"), ("BPK", "143"), ("BPK", "205"), ("STAT", "201")],
    ),
  ],
)
def test_course_codes_found(text, codes):
  assert prerequisite_codes(text, DEPARTMENTS) == codes


@pytest.mark.parametrize(
  "text",
  [
    "A minimum of 100 units and permission of the chair.",
    "BC Mathematics 12 (or equivalent) or any 100-level MATH course with a minimum grade of C.",
    "EASC 101 and six units in any 200-division or higher EASC courses",
  ],
)
def test_unit_counts_and_levels_are_not_courses(text):
  assert all(number not in {"100", "200"} for _, number in prerequisite_codes(text, DEPARTMENTS))


def test_unknown_code_before_number_stops_carry_over():
  codes = prerequisite_codes("ARCH 100, ARCH 201, HS 100, HS 231, HIST 277", DEPARTMENTS)
  assert codes == [("ARCH", "100"), ("ARCH", "201"), ("HIST", "277")]


def test_unknown_code_in_parentheses_is_skipped():
  assert prerequisite_codes("CA (or FPA) 122.", DEPARTMENTS) == [("CA", "122")]


def test_corequisites_ignored():
  text = "CA (or FPA) 122. Corequisite: CA 123 and CA 124 must be taken concurrently."
  assert prerequisite_codes(text, DEPARTMENTS) == [("CA", "122")]


def test_sentence_break_stops_carry_over():
  assert prerequisite_codes("MATH 151. 100 students max", DEPARTMENTS) == [("MATH", "151")]


# build_unlocks_index / find_outline


def test_index_maps_prerequisites_to_courses(samples):
  index = build_unlocks_index(samples)
  unlocked = {f"{o['dept']} {o['number']}" for o in index[("CMPT", "225")]}
  assert {"CMPT 300", "CMPT 307"} <= unlocked
  assert "CMPT 225" not in unlocked


def test_index_skips_a_course_listing_itself():
  outline = {"dept": "CMPT", "number": "225", "title": "DS", "prerequisites": "CMPT 225 (or equivalent)"}
  assert ("CMPT", "225") not in build_unlocks_index([outline])


def test_find_outline_normalizes_input(samples):
  assert find_outline(samples, " cmpt ", "225 ")["title"] == "Data Structures and Programming"
  assert find_outline(samples, "CMPT", "999") is None


# build_unlocks_embed


def outline(dept, number, title="T"):
  return {"dept": dept, "number": number, "title": title}


def test_embed_groups_own_department_first_then_alphabetical():
  unlocked = [outline("MACM", "401"), outline("CMPT", "307"), outline("ENSC", "351"), outline("MACM", "201")]
  embed = build_unlocks_embed(outline("MACM", "101"), unlocked)
  assert embed.title == "What MACM 101 unlocks"
  assert embed.description.splitlines() == [
    "**MACM**",
    "MACM 201 · T",
    "MACM 401 · T",
    "**CMPT**",
    "CMPT 307 · T",
    "**ENSC**",
    "ENSC 351 · T",
  ]
  assert embed.footer.text.startswith("4 courses mention MACM 101")


def test_embed_sorts_numbers_numerically():
  embed = build_unlocks_embed(
    outline("CMPT", "120"), [outline("CMPT", "1000"), outline("CMPT", "225"), outline("CMPT", "105W")]
  )
  assert embed.description.splitlines()[1:] == ["CMPT 105W · T", "CMPT 225 · T", "CMPT 1000 · T"]


def test_embed_when_nothing_unlocked():
  embed = build_unlocks_embed(outline("CMPT", "999"), [])
  assert embed.description == "No courses list CMPT 999 as a prerequisite."
  assert embed.footer.text is None
