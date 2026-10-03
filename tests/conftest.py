import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_env():
  return {
    'DISCORD_TOKEN': 'token',
    'GUILD_ID': '1',
    'STUDY_TIME_VC_CHANNEL_ID': '2',
    'STUDY_TIME_TEXT_CHANNEL_ID': '3',
    'MODERATION_REPORT_VC_CHANNEL_ID': '4',
    'STUDY_TIME_ROLE_NAME': 'Study Time',
  }


@pytest.fixture
def load_fixture():
  """Load a real SFU API response saved in tests/fixtures/, e.g. load_fixture("sections_cmpt225")."""

  def _load(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text())

  return _load
