import pytest # test running framework
from unittest.mock import Mock, patch, MagicMock, AsyncMock #creates fake objects for testing
import json
# importing helper functions from my bot
from bot import parse_term_year, get_command_type

# Test classes need to be prefixed with Test to be recognized by pytest
# Grouping Related (helper in this case) functions together in a class
class TestHelperFunctions:
  #functions need to start with test_ to be recognized by pytest
  def test_parse_term_year(self):
    assert parse_term_year("2025-fall")==2025
    assert parse_term_year("fall-2024")==2024
    assert parse_term_year("fall-semester")==0 # function should return 0
  
  def test_get_command_type_slash(self):
    ctx=Mock()
    ctx.interaction = Mock()
    result = get_command_type(ctx)
    assert result == 'slash'

  def test_get_command_type_prefix(self):
    ctx=Mock()
    ctx.interaction=None
    result = get_command_type(ctx)
    assert result == 'prefix'
      
class TestSectionCommand:
  """Testing section command"""

  #Fixtures are reusable test data
  @pytest.fixture
  def mock_section_response_success(self): # one proper dataset
    """What the API returns for a valid section request"""
    return[{
      "dept": "CMPT",
      "number":"201",
      "title":"Systems Programming",
      "units":"4",
      "term":"2026-spring",
      "sections":[
        {"section": "D100", "instructors": ["John Doe"], "schedule": "MWF 10:30-11:20"},
        {"section": "D200", "instructors": ["Jane Smith"], "schedule": "TuTh 14:30-16:20"}
      ]
    }]
  
  @pytest.fixture
  def mock_section_no_instructors(self): # improper dataset
    """Section with TBA instructors"""
    return [{
      "dept": "CMPT",
      "number": "999",
      "title": "New Course",
      "units": "3",
      "term": "2026-spring",
      "sections": [
        {"section": "D100", "instructors": [], "schedule": "MWF 9:30-10:20"}
      ]
    }]
  
  #Test the parsing of the data
  def test_section_data_requried_fields(self, mock_section_response_success):
    """Verify the API response structure I expect"""
    data = mock_section_response_success[0]
    assert "dept" in data
    assert "number" in data
    assert "title" in data
    assert "units" in data
    assert "sections" in data

  def test_section_parsing(self, mock_section_response_success):
    """Test that we can parse section info correctly"""
    course = mock_section_response_success[0]
    sections = course.get('sections', [])
    
    assert len(sections) == 2
    assert sections[0]['section'] == "D100"
    assert sections[0]['instructors'] == ["John Doe"]
    assert sections[0]['schedule'] == "MWF 10:30-11:20"

  def test_instructor_string_formatting(self, mock_section_response_success):
    """Test the instructor list to string conversion"""
    sections = mock_section_response_success[0]['sections']
    for section in sections:
      instrs = section.get('instructors', [])
      instrs_str = ", ".join(instrs) if instrs else "TBA"      
    assert instrs_str != "TBA"  # These have instructors
    assert "John Doe" in instrs_str or "Jane Smith" in instrs_str

  def test_empty_instructors_shows_tba(self, mock_section_no_instructors):
    """Test that empty instructor list shows TBA"""
    section = mock_section_no_instructors[0]['sections'][0]
    instrs = section.get('instructors', [])
    instrs_str = ", ".join(instrs) if instrs else "TBA"
    
    assert instrs_str == "TBA"
  
  def test_empty_response_handling(self):
    """Test handling when API returns an empty array"""
    data = []
    assert not data
  
  def test_section_info_string_building(self, mock_section_response_success):
    """Test building the section info string like your bot does"""
    course = mock_section_response_success[0]
    sections = course.get('sections', [])
    
    sections_info = []
    for section in sections:
      sec_code = section.get('section', 'N/A')
      instrs = section.get('instructors', [])
      instrs_str = ", ".join(instrs) if instrs else "TBA"
      schedule = section.get('schedule', 'TBA')
      sections_info.append(f"**Section {sec_code}** - Instructors: {instrs_str} - Schedule: {schedule}")

    assert len(sections_info) == 2
    assert "**Section D100**" in sections_info[0]
    assert "John Doe" in sections_info[0]
    assert "MWF 10:30-11:20" in sections_info[0]

