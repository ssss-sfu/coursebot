from unittest.mock import Mock

from bot import get_command_type


def test_get_command_type_slash():
  ctx = Mock()
  ctx.interaction = Mock()
  assert get_command_type(ctx) == 'slash'


def test_get_command_type_prefix():
  ctx = Mock()
  ctx.interaction = None
  assert get_command_type(ctx) == 'prefix'
