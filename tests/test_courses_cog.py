from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp import web

from src.cogs.courses import Courses
from src.courses.presentation import DESCRIPTION_LIMIT, FIELD_VALUE_LIMIT, parse_term_year
from src.sfu_api import SFUClient


def make_interaction():
  """A stand-in for discord.Interaction that records defer/send in order."""
  interaction = Mock()
  interaction.calls = []

  async def defer(*args, **kwargs):
    interaction.calls.append("defer")

  async def send(*args, **kwargs):
    interaction.calls.append("send")

  interaction.response.defer = AsyncMock(side_effect=defer)
  interaction.followup.send = AsyncMock(side_effect=send)
  return interaction


def sent(interaction):
  """(text, embed) from the single followup message."""
  interaction.followup.send.assert_awaited_once()
  call = interaction.followup.send.call_args
  text = call.args[0] if call.args else call.kwargs.get("content")
  return text, call.kwargs.get("embed")


@pytest.fixture
def cog(api, session):
  return Courses(SFUClient(session, api.base_url))


@pytest.fixture
def cmpt120(load_fixture):
  return load_fixture("outlines_cmpt120")


def outline(**overrides):
  base = {
    "dept": "CMPT",
    "number": "120",
    "title": "Intro",
    "description": "A course.",
    "units": "3",
    "prerequisites": "",
    "offerings": [],
  }
  return [{**base, **overrides}]


async def run_course(cog, interaction, subject, number):
  await cog.course.callback(cog, interaction, subject, number)


# /course


@pytest.mark.asyncio
async def test_course_success_builds_embed(cog, api, cmpt120):
  api.respond(lambda: web.json_response(cmpt120))
  interaction = make_interaction()
  await run_course(cog, interaction, "CMPT", "120")

  assert interaction.calls == ["defer", "send"]
  _, embed = sent(interaction)
  course = cmpt120[0]
  assert embed.title == f"{course['dept']} {course['number']}: {course['title']}"
  assert embed.description == course["description"]
  fields = {f.name: f.value for f in embed.fields}
  assert fields["Credits"] == str(course["units"])
  assert fields["Prerequisites"] == (course["prerequisites"] or "None")


@pytest.mark.asyncio
async def test_course_shows_four_most_recent_offerings(cog, api, cmpt120):
  api.respond(lambda: web.json_response(cmpt120))
  interaction = make_interaction()
  await run_course(cog, interaction, "CMPT", "120")

  _, embed = sent(interaction)
  lines = next(f.value for f in embed.fields if f.name == "Recent Offerings").splitlines()
  expected_count = min(4, len(cmpt120[0]["offerings"]))
  assert len(lines) == expected_count
  years = [parse_term_year(line) for line in lines]
  assert years == sorted(years, reverse=True)


@pytest.mark.asyncio
async def test_course_sends_dept_and_number_to_api(cog, api, cmpt120):
  api.respond(lambda: web.json_response(cmpt120))
  await run_course(cog, make_interaction(), "CMPT", " 120 ")
  assert api.requests[0].path == "/v1/rest/outlines"
  assert api.requests[0].query["dept"] == "CMPT"
  assert api.requests[0].query["number"] == "120"


@pytest.mark.asyncio
async def test_course_alphanumeric_number_accepted(cog, api):
  api.respond(lambda: web.json_response(outline(number="105W")))
  interaction = make_interaction()
  await run_course(cog, interaction, "CMPT", "105W")
  _, embed = sent(interaction)
  assert embed.title.startswith("CMPT 105W")


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [lambda: web.Response(status=404), lambda: web.json_response([])])
async def test_course_not_found(cog, api, response):
  api.respond(response)
  interaction = make_interaction()
  await run_course(cog, interaction, "cmpt", "999")
  text, embed = sent(interaction)
  assert text == "No course data found for CMPT 999."
  assert embed is None


@pytest.mark.asyncio
async def test_course_67_easter_egg(cog, api):
  api.respond(lambda: web.json_response([]))
  interaction = make_interaction()
  await run_course(cog, interaction, "CMPT", "67")
  text, _ = sent(interaction)
  assert text == "67"


@pytest.mark.asyncio
@pytest.mark.parametrize("number", ["abc", "12-3", "", "W105"])
async def test_course_invalid_number_skips_api(cog, api, number):
  interaction = make_interaction()
  await run_course(cog, interaction, "CMPT", number)
  text, _ = sent(interaction)
  assert text.startswith("Invalid course number format")
  assert interaction.calls == ["defer", "send"]
  assert api.requests == []


@pytest.mark.asyncio
async def test_course_api_error(cog, api):
  api.respond(lambda: web.Response(status=500))
  interaction = make_interaction()
  await run_course(cog, interaction, "CMPT", "120")
  text, embed = sent(interaction)
  assert text == "An unexpected error occurred while fetching course outlines."
  assert embed is None


@pytest.mark.asyncio
async def test_course_without_offerings(cog, api):
  api.respond(lambda: web.json_response(outline(offerings=[])))
  interaction = make_interaction()
  await run_course(cog, interaction, "CMPT", "120")
  _, embed = sent(interaction)
  fields = {f.name: f.value for f in embed.fields}
  assert fields["Recent Offerings Found"] == "No offerings available"


@pytest.mark.asyncio
async def test_course_offering_without_instructors(cog, api):
  api.respond(lambda: web.json_response(outline(offerings=[{"term": "Fall 2026", "instructors": []}])))
  interaction = make_interaction()
  await run_course(cog, interaction, "CMPT", "120")
  _, embed = sent(interaction)
  recent = next(f.value for f in embed.fields if f.name == "Recent Offerings")
  assert recent == "• **Fall 2026 - No instructors listed**"


@pytest.mark.asyncio
async def test_course_missing_prerequisites_shows_none(cog, api):
  api.respond(lambda: web.json_response(outline(prerequisites="")))
  interaction = make_interaction()
  await run_course(cog, interaction, "CMPT", "120")
  _, embed = sent(interaction)
  assert {f.name: f.value for f in embed.fields}["Prerequisites"] == "None"


# /offerings


async def run_offerings(cog, interaction, name, term=None):
  await cog.offerings.callback(cog, interaction, name, term)


def instructor(name="Jane Smith", offerings=None):
  return {"name": name, "offerings": offerings or []}


def offering(dept="CMPT", number="120", title="Intro", term="Fall 2026"):
  return {"dept": dept, "number": number, "title": title, "term": term}


@pytest.fixture
def fraser(load_fixture):
  return load_fixture("instructors_fraser")


@pytest.mark.asyncio
async def test_offerings_success_lists_every_offering(cog, api, fraser):
  api.respond(lambda: web.json_response(fraser))
  interaction = make_interaction()
  await run_offerings(cog, interaction, "Brian Fraser")

  assert interaction.calls == ["defer", "send"]
  _, embed = sent(interaction)
  assert embed.title == "Courses taught by Brian Fraser"
  lines = embed.description.splitlines()
  assert len(lines) == len(fraser[0]["offerings"])
  first = fraser[0]["offerings"][0]
  assert lines[0] == f"**{first['dept']} {first['number']}** - {first['title']} ({first['term']})"


@pytest.mark.asyncio
async def test_offerings_sends_name_to_api(cog, api, fraser):
  api.respond(lambda: web.json_response(fraser))
  await run_offerings(cog, make_interaction(), "Brian Fraser")
  assert api.requests[0].path == "/v1/rest/instructors"
  assert api.requests[0].query["name"] == "Brian Fraser"


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [lambda: web.Response(status=404), lambda: web.json_response([])])
async def test_offerings_not_found_includes_name(cog, api, response):
  api.respond(response)
  interaction = make_interaction()
  await run_offerings(cog, interaction, "Zzzz Notaprof")
  _, embed = sent(interaction)
  assert embed.title == "No Instructors Found"
  assert "Zzzz Notaprof" in embed.description


@pytest.mark.asyncio
async def test_offerings_multiple_matches_lists_up_to_ten(cog, api):
  matches = [instructor(name=f"Smith {i}") for i in range(12)]
  api.respond(lambda: web.json_response(matches))
  interaction = make_interaction()
  await run_offerings(cog, interaction, "Smith")
  _, embed = sent(interaction)
  assert embed.title == "Multiple Instructors Found"
  assert "Found 12 instructors" in embed.description
  assert embed.fields[0].value.splitlines() == [f"• Smith {i}" for i in range(10)]
  assert embed.footer.text == "Tip: Retry /offerings with the instructor's full name."


@pytest.mark.asyncio
async def test_offerings_term_filter_is_case_insensitive(cog, api):
  offerings = [offering(number="120", term="Fall 2026"), offering(number="225", term="Spring 2026")]
  api.respond(lambda: web.json_response([instructor(offerings=offerings)]))
  interaction = make_interaction()
  await run_offerings(cog, interaction, "Jane Smith", "FALL")
  _, embed = sent(interaction)
  assert "CMPT 120" in embed.description
  assert "CMPT 225" not in embed.description


@pytest.mark.asyncio
async def test_offerings_term_with_no_matches(cog, api):
  api.respond(lambda: web.json_response([instructor(offerings=[offering(term="Fall 2026")])]))
  interaction = make_interaction()
  await run_offerings(cog, interaction, "Jane Smith", "summer")
  _, embed = sent(interaction)
  assert embed.title == "No Offerings Found for Specified Term"
  assert "'summer'" in embed.description


@pytest.mark.asyncio
async def test_offerings_instructor_without_offerings(cog, api):
  api.respond(lambda: web.json_response([instructor(offerings=[])]))
  interaction = make_interaction()
  await run_offerings(cog, interaction, "Jane Smith")
  _, embed = sent(interaction)
  assert embed.description == "No offerings found."


@pytest.mark.asyncio
async def test_offerings_huge_list_fits_description_limit(cog, api):
  many = [offering(number=str(100 + i), title="A Very Long Course Title " * 3) for i in range(300)]
  api.respond(lambda: web.json_response([instructor(offerings=many)]))
  interaction = make_interaction()
  await run_offerings(cog, interaction, "Jane Smith")
  _, embed = sent(interaction)
  assert len(embed.description) <= DESCRIPTION_LIMIT
  assert embed.description.splitlines()[-1].endswith("more")


@pytest.mark.asyncio
async def test_offerings_api_error(cog, api):
  api.respond(lambda: web.Response(status=503))
  interaction = make_interaction()
  await run_offerings(cog, interaction, "Brian Fraser")
  _, embed = sent(interaction)
  assert embed.title == "Server Error"


# /section


async def run_section(cog, interaction, year=2026, term="fall", dept="CMPT", number="225"):
  await cog.section.callback(cog, interaction, year, term, dept, number)


@pytest.fixture
def cmpt225(load_fixture):
  return load_fixture("sections_cmpt225")


@pytest.mark.asyncio
async def test_section_success_with_real_data(cog, api, cmpt225):
  api.respond(lambda: web.json_response(cmpt225))
  interaction = make_interaction()
  await run_section(cog, interaction)

  assert interaction.calls == ["defer", "send"]
  _, embed = sent(interaction)
  course = cmpt225[0]
  assert embed.title == f"{course['dept']} {course['number']}: {course['title']} (2026-fall)"
  assert embed.description == f"Units: {course['units']}"
  field = embed.fields[0].value
  assert len(field) <= FIELD_VALUE_LIMIT
  assert field.startswith(f"**Section {course['sections'][0]['section']}**")
  assert "{" not in field  # no raw instructor/schedule dicts


@pytest.mark.asyncio
async def test_section_real_cmpt225_is_truncated(cog, api, cmpt225):
  # the full 14-section list is 1,075 characters, over Discord's 1,024 field limit
  api.respond(lambda: web.json_response(cmpt225))
  interaction = make_interaction()
  await run_section(cog, interaction)
  _, embed = sent(interaction)
  assert embed.fields[0].value.splitlines()[-1].startswith("…and ")


@pytest.mark.asyncio
async def test_section_sends_params_to_api(cog, api, cmpt225):
  api.respond(lambda: web.json_response(cmpt225))
  await run_section(cog, make_interaction(), 2026, "fall", "CMPT", "225")
  query = api.requests[0].query
  assert api.requests[0].path == "/v1/rest/sections"
  assert (query["term"], query["dept"], query["number"]) == ("2026-fall", "CMPT", "225")


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [lambda: web.Response(status=404), lambda: web.json_response([])])
async def test_section_not_found(cog, api, response):
  api.respond(response)
  interaction = make_interaction()
  await run_section(cog, interaction, 2026, "autumn", "CMPT", "225")
  _, embed = sent(interaction)
  assert embed.title == "No Sections Found"
  assert embed.description == "No sections found for CMPT 225 in 2026-autumn"


@pytest.mark.asyncio
async def test_section_course_without_sections(cog, api):
  api.respond(
    lambda: web.json_response([{"dept": "CMPT", "number": "225", "title": "DS", "units": "3", "sections": []}])
  )
  interaction = make_interaction()
  await run_section(cog, interaction)
  _, embed = sent(interaction)
  assert embed.fields[0].value == "No sections available"


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "title"), [(400, "Try Again"), (500, "Server Error"), (503, "Server Error")])
async def test_section_api_errors(cog, api, status, title):
  api.respond(lambda: web.Response(status=status))
  interaction = make_interaction()
  await run_section(cog, interaction)
  _, embed = sent(interaction)
  assert embed.title == title


# /reviews


async def run_reviews(cog, interaction, name):
  await cog.reviews.callback(cog, interaction, name)


@pytest.fixture
def fraser_reviews(load_fixture):
  return load_fixture("reviews_fraser")


@pytest.mark.asyncio
async def test_reviews_success_with_real_entry(cog, api, fraser_reviews):
  api.respond(lambda: web.json_response(fraser_reviews))
  interaction = make_interaction()
  await run_reviews(cog, interaction, "Brian Fraser")

  assert interaction.calls == ["defer", "send"]
  _, embed = sent(interaction)
  prof = fraser_reviews[0]
  assert embed.title == "Reviews for Brian Fraser"
  assert embed.url == prof["URL"]
  assert prof["Department"] in embed.description
  info = embed.fields[0].value
  assert f"Rating: {prof['Quality']}/5" in info
  assert f"Difficulty: {prof['Difficulty']}/5" in info
  assert f"Ratings: {prof['Ratings']}" in info
  assert f"{prof['WouldTakeAgain']} of students Would Take Again" in info


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["brian fraser", "BRIAN FRASER", "  Brian Fraser  "])
async def test_reviews_name_match_ignores_case_and_spaces(cog, api, fraser_reviews, name):
  api.respond(lambda: web.json_response(fraser_reviews))
  interaction = make_interaction()
  await run_reviews(cog, interaction, name)
  _, embed = sent(interaction)
  assert embed.title == "Reviews for Brian Fraser"


@pytest.mark.asyncio
async def test_reviews_not_found(cog, api, fraser_reviews):
  api.respond(lambda: web.json_response(fraser_reviews))
  interaction = make_interaction()
  await run_reviews(cog, interaction, "Zzzz Notaprof")
  _, embed = sent(interaction)
  assert embed.title == "No Reviews Found"
  assert "'Zzzz Notaprof'" in embed.description


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [lambda: web.Response(status=404), lambda: web.json_response([])])
async def test_reviews_no_data(cog, api, response):
  api.respond(response)
  interaction = make_interaction()
  await run_reviews(cog, interaction, "Brian Fraser")
  _, embed = sent(interaction)
  assert embed.title == "No Data Available"


@pytest.mark.asyncio
async def test_reviews_api_error(cog, api):
  api.respond(lambda: web.Response(status=500))
  interaction = make_interaction()
  await run_reviews(cog, interaction, "Brian Fraser")
  _, embed = sent(interaction)
  assert embed.title == "Error"


@pytest.mark.asyncio
async def test_reviews_without_url(cog, api, fraser_reviews):
  entry = {**fraser_reviews[0], "URL": ""}
  api.respond(lambda: web.json_response([entry]))
  interaction = make_interaction()
  await run_reviews(cog, interaction, "Brian Fraser")
  _, embed = sent(interaction)
  assert embed.url is None


@pytest.mark.asyncio
async def test_reviews_second_call_uses_cache(cog, api, fraser_reviews):
  api.respond(lambda: web.json_response(fraser_reviews))  # only one response queued
  await run_reviews(cog, make_interaction(), "Brian Fraser")
  interaction = make_interaction()
  await run_reviews(cog, interaction, "Brian Fraser")
  _, embed = sent(interaction)
  assert embed.title == "Reviews for Brian Fraser"
  assert len(api.requests) == 1
