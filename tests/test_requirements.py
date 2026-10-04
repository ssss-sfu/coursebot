import pytest

from src.courses.requirements import build_find_embed, course_level, filter_courses, parse_designation


@pytest.fixture
def samples(load_fixture):
  return load_fixture("outlines_find_samples")


def codes(outlines):
  return [f"{o['dept']} {o['number']}" for o in outlines]


# parse_designation


@pytest.mark.parametrize(
  ("designation", "expected"),
  [
    ("Writing/Breadth-Hum/Soc Sci", {"W", "B-Hum", "B-Soc"}),
    ("Q/Breadth-Social Sci/Sciences", {"Q", "B-Soc", "B-Sci"}),
    ("Breadth-Humanities/Sciences", {"B-Hum", "B-Sci"}),
    ("Quantitative/Breadth-Soc", {"Q", "B-Soc"}),
    ("N/A", set()),
    ("", set()),
  ],
)
def test_parse_designation(designation, expected):
  assert parse_designation(designation) == expected


def test_every_real_designation_is_understood(load_fixture):
  # every designation string that exists in the API, except the empty ones, must map to something
  for designation in load_fixture("designations"):
    if designation not in ("", "N/A"):
      assert parse_designation(designation), designation


# course_level


@pytest.mark.parametrize(("number", "level"), [("105W", 100), ("376", 300), ("X91", None)])
def test_course_level(number, level):
  assert course_level(number) == level


# filter_courses (real outlines)


def test_requirement_filter(samples):
  assert codes(filter_courses(samples, requirement="W")) == [
    "ACMA 360W",
    "ARCH 272W",
    "ARCH 471W",
    "CA 257W",
    "CMPT 376W",
    "DIAL 390W",
    "ENSC 100W",
  ]


def test_filters_combine(samples):
  matches = filter_courses(samples, requirement="B-Soc", delivery="Online", no_prereqs=True)
  assert codes(matches) == ["ARCH 100", "ARCH 226"]


def test_no_prereqs_filter(samples):
  assert codes(filter_courses(samples, dept="ACMA", no_prereqs=True)) == ["ACMA 101"]


def test_dept_and_level_filters(samples):
  assert codes(filter_courses(samples, dept=" acma ", level=300)) == ["ACMA 360W"]


def test_term_filter(samples):
  assert codes(filter_courses(samples, dept="ENSC", term="Fall 2025")) == ["ENSC 100W"]
  assert filter_courses(samples, dept="ENSC", term="Spring 2027") == []


def test_graduate_courses_excluded(samples):
  assert all(o["degreeLevel"] == "UGRD" for o in filter_courses(samples, dept="ACMA"))
  assert "ACMA 830" not in codes(filter_courses(samples, no_prereqs=True))


# build_find_embed


def test_embed_lines_show_tags_and_delivery(samples):
  embed = build_find_embed(filter_courses(samples, dept="ARCH", delivery="Online"), ["ARCH", "Online"])
  assert embed.title == "Courses: ARCH · Online"
  assert embed.description.splitlines()[0].startswith("**ARCH 100** ")
  assert embed.description.splitlines()[0].endswith(" · B-Soc · Online")
  assert embed.footer.text == "2 courses"


def test_embed_single_match_footer(samples):
  embed = build_find_embed(filter_courses(samples, dept="CMPT", level=300), ["CMPT", "300-level"])
  assert embed.footer.text == "1 course"


def test_embed_when_nothing_matches():
  embed = build_find_embed([], ["W", "CMPT", "100-level"])
  assert embed.description == "No undergraduate courses match those filters."
  assert embed.footer.text is None


def test_embed_truncates_long_results():
  many = [
    {"dept": "CMPT", "number": str(100 + i), "title": "A Fairly Long Course Title " * 3, "designation": "Writing"}
    for i in range(300)
  ]
  embed = build_find_embed(many, ["W"])
  assert len(embed.description) <= 4096
  assert embed.description.splitlines()[-1].startswith("…and ")
  assert embed.footer.text == "300 courses · narrow your filters to see the rest"
