import pytest


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
