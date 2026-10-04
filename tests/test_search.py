import pytest

from src.courses.search import MAX_AUTOCOMPLETE_CHOICES, filter_departments, suggest_names

DEPARTMENTS = ["ACMA", "BUS", "CHEM", "CMNS", "CMPT", "MACM", "MATH", "STAT"]


# filter_departments


def test_prefix_matches_come_before_substring_matches():
  assert filter_departments(DEPARTMENTS, "m") == ["MACM", "MATH", "ACMA", "CHEM", "CMNS", "CMPT"]


def test_query_is_case_insensitive_and_trimmed():
  assert filter_departments(DEPARTMENTS, " cmp ") == ["CMPT"]


def test_results_capped_at_limit():
  many = [f"D{i:03}" for i in range(100)]
  assert len(filter_departments(many, "")) == MAX_AUTOCOMPLETE_CHOICES
  assert len(filter_departments(many, "d", limit=5)) == 5


# suggest_names

NAMES = ["Brian Fraser", "Diana Cukierman", "Toby Donaldson", "Jason Brown", "jason brown"]


@pytest.mark.parametrize(
  ("query", "expected"),
  [
    ("Brian Frazer", ["Brian Fraser"]),  # typo
    ("  CUKIERMAN  ", ["Diana Cukierman"]),  # last name only
  ],
)
def test_suggests_close_names(query, expected):
  assert suggest_names(query, NAMES) == expected


def test_last_name_of_long_name_found_by_substring():
  # too short to be a close spelling of the whole name, so only the substring fallback can find it
  assert suggest_names("fraser", ["Maximilian Alexander Fraser"]) == ["Maximilian Alexander Fraser"]


def test_shared_first_name_alone_is_not_suggested():
  names = ["Brian Fraser", "Brian Krauth", "Brian Hayden"]
  assert suggest_names("Brian Frazer", names) == ["Brian Fraser"]
