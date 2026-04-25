"""
Tests for assignment-related MCP tools.

Includes tests for:
- list_assignments
- get_assignment_details
- list_submissions
- get_assignment_analytics
- create_assignment
- update_assignment
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_canvas_api():
    """Fixture to mock Canvas API calls for assignment tools."""
    with patch('canvas_mcp.tools.assignments.get_course_id') as mock_get_id, \
         patch('canvas_mcp.tools.assignments.get_course_code') as mock_get_code, \
         patch('canvas_mcp.tools.assignments.fetch_all_paginated_results') as mock_fetch, \
         patch('canvas_mcp.tools.assignments.make_canvas_request') as mock_request:

        mock_get_id.return_value = "60366"
        mock_get_code.return_value = "badm_350_120251"

        yield {
            'get_course_id': mock_get_id,
            'get_course_code': mock_get_code,
            'fetch_all_paginated_results': mock_fetch,
            'make_canvas_request': mock_request
        }


def get_tool_function(tool_name: str):
    """Get a tool function by name from the registered tools."""
    from mcp.server.fastmcp import FastMCP

    from canvas_mcp.tools.assignments import register_assignment_tools

    # Create a mock MCP server and register tools
    mcp = FastMCP("test")

    # Store captured functions
    captured_functions = {}

    # Override the tool decorator to capture the function
    original_tool = mcp.tool

    def capturing_tool(*args, **kwargs):
        decorator = original_tool(*args, **kwargs)
        def wrapper(fn):
            captured_functions[fn.__name__] = fn
            return decorator(fn)
        return wrapper

    mcp.tool = capturing_tool
    register_assignment_tools(mcp)

    return captured_functions.get(tool_name)


# --- Mock data for list_assignments tests ---

MOCK_ASSIGNMENTS = [
    {
        "id": 101,
        "name": "EDA Notebook",
        "due_at": "2026-04-20T23:59:00Z",
        "points_possible": 50,
        "published": True,
        "assignment_group_id": 10,
        "created_at": "2026-04-01T00:00:00Z",
        "has_overrides": False,
        "description": "<p>Explore the dataset.</p>",
        "rubric": [{"id": "r1", "points": 50, "description": "Quality"}],
        "rubric_settings": {"points_possible": 50},
    },
    {
        "id": 102,
        "name": "Final Report",
        "due_at": "2026-04-28T23:59:00Z",
        "points_possible": 100,
        "published": True,
        "assignment_group_id": 10,
        "created_at": "2026-04-05T00:00:00Z",
        "has_overrides": False,
        "description": "<p>Write the final report.</p>",
        "rubric": None,
        "rubric_settings": None,
    },
    {
        "id": 103,
        "name": "Draft Outline",
        "due_at": None,
        "points_possible": 0,
        "published": False,
        "assignment_group_id": 11,
        "created_at": "2026-04-10T00:00:00Z",
        "has_overrides": False,
        "description": "<p>Submit an outline draft.</p>",
        "rubric": None,
        "rubric_settings": None,
    },
    {
        "id": 104,
        "name": "Midterm Quiz",
        "due_at": "2026-04-15T23:59:00Z",
        "points_possible": 25,
        "published": True,
        "assignment_group_id": 12,
        "created_at": "2026-03-20T00:00:00Z",
        "has_overrides": False,
        "description": "",
        "rubric": None,
        "rubric_settings": None,
    },
]


class TestListAssignments:
    """Tests for list_assignments tool with filtering and pagination."""

    # --- Unit 1: Parameters and Canvas API pass-through ---

    @pytest.mark.asyncio
    async def test_default_params_unchanged(self, mock_canvas_api):
        """Call with no new params behaves identically to current behavior."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = MOCK_ASSIGNMENTS

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251")

        # Verify fetch_all_paginated_results was used (not make_canvas_request)
        mock_canvas_api['fetch_all_paginated_results'].assert_called_once()
        call_args = mock_canvas_api['fetch_all_paginated_results'].call_args
        assert call_args[0][0] == "/courses/60366/assignments"
        params = call_args[0][1]
        assert params["per_page"] == 100
        assert "include[]" in params

        # Verify output contains all assignments
        assert "EDA Notebook" in result
        assert "Final Report" in result
        assert "Draft Outline" in result
        assert "Midterm Quiz" in result

    @pytest.mark.asyncio
    async def test_search_term_passed_to_api(self, mock_canvas_api):
        """search_term appears in params passed to fetch_all_paginated_results."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = [MOCK_ASSIGNMENTS[0]]

        list_assignments = get_tool_function('list_assignments')
        await list_assignments("badm_350_120251", search_term="EDA")

        call_args = mock_canvas_api['fetch_all_paginated_results'].call_args
        params = call_args[0][1]
        assert params["search_term"] == "EDA"

    @pytest.mark.asyncio
    async def test_per_page_custom_value(self, mock_canvas_api):
        """per_page=50 is passed to Canvas API params."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = MOCK_ASSIGNMENTS

        list_assignments = get_tool_function('list_assignments')
        await list_assignments("badm_350_120251", per_page=50)

        call_args = mock_canvas_api['fetch_all_paginated_results'].call_args
        params = call_args[0][1]
        assert params["per_page"] == 50

    @pytest.mark.asyncio
    async def test_page_uses_single_request(self, mock_canvas_api):
        """page param triggers make_canvas_request instead of fetch_all_paginated_results."""
        mock_canvas_api['make_canvas_request'].return_value = [MOCK_ASSIGNMENTS[0], MOCK_ASSIGNMENTS[1]]

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251", page=2, per_page=25)

        # Should use make_canvas_request, NOT fetch_all_paginated_results
        mock_canvas_api['make_canvas_request'].assert_called_once()
        mock_canvas_api['fetch_all_paginated_results'].assert_not_called()

        call_args = mock_canvas_api['make_canvas_request'].call_args
        assert call_args[0][0] == "get"
        assert "/courses/60366/assignments" in call_args[0][1]
        params = call_args[1]["params"]
        assert params["page"] == 2
        assert params["per_page"] == 25

        assert "EDA Notebook" in result

    @pytest.mark.asyncio
    async def test_per_page_zero_returns_error(self, mock_canvas_api):
        """per_page=0 returns a validation error."""
        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251", per_page=0)

        assert "Invalid per_page" in result
        mock_canvas_api['fetch_all_paginated_results'].assert_not_called()
        mock_canvas_api['make_canvas_request'].assert_not_called()

    @pytest.mark.asyncio
    async def test_per_page_over_100_returns_error(self, mock_canvas_api):
        """per_page=200 returns a validation error."""
        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251", per_page=200)

        assert "Invalid per_page" in result
        mock_canvas_api['fetch_all_paginated_results'].assert_not_called()

    # --- Unit 2: Client-side filtering (dates, published) ---

    @pytest.mark.asyncio
    async def test_due_after_filter(self, mock_canvas_api):
        """due_after filters out assignments before the date."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = MOCK_ASSIGNMENTS

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251", due_after="2026-04-18")

        # EDA Notebook (Apr 20) and Final Report (Apr 28) pass, Midterm (Apr 15) excluded
        # Draft Outline (no due date) excluded
        assert "EDA Notebook" in result
        assert "Final Report" in result
        assert "Midterm Quiz" not in result
        assert "Draft Outline" not in result

    @pytest.mark.asyncio
    async def test_due_before_filter(self, mock_canvas_api):
        """due_before filters out assignments after the date."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = MOCK_ASSIGNMENTS

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251", due_before="2026-04-21")

        # EDA Notebook (Apr 20) and Midterm (Apr 15) pass, Final Report (Apr 28) excluded
        assert "EDA Notebook" in result
        assert "Midterm Quiz" in result
        assert "Final Report" not in result
        assert "Draft Outline" not in result

    @pytest.mark.asyncio
    async def test_date_range_filter(self, mock_canvas_api):
        """Combined due_after and due_before narrows to a date window."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = MOCK_ASSIGNMENTS

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments(
            "badm_350_120251",
            due_after="2026-04-18",
            due_before="2026-04-25",
        )

        # Only EDA Notebook (Apr 20) falls in the window
        assert "EDA Notebook" in result
        assert "Final Report" not in result
        assert "Midterm Quiz" not in result

    @pytest.mark.asyncio
    async def test_published_only_filter(self, mock_canvas_api):
        """published_only=True excludes unpublished assignments."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = MOCK_ASSIGNMENTS

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251", published_only=True)

        assert "EDA Notebook" in result
        assert "Final Report" in result
        assert "Midterm Quiz" in result
        assert "Draft Outline" not in result  # unpublished

    @pytest.mark.asyncio
    async def test_combined_date_and_published_filters(self, mock_canvas_api):
        """Both date and published filters applied together."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = MOCK_ASSIGNMENTS

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments(
            "badm_350_120251",
            published_only=True,
            due_after="2026-04-18",
        )

        # EDA Notebook (published, Apr 20) and Final Report (published, Apr 28) pass
        # Draft Outline (unpublished) and Midterm (before Apr 18) excluded
        assert "EDA Notebook" in result
        assert "Final Report" in result
        assert "Midterm Quiz" not in result
        assert "Draft Outline" not in result

    @pytest.mark.asyncio
    async def test_no_due_date_excluded_by_date_filter(self, mock_canvas_api):
        """Assignments with due_at=None are excluded when date filtering is active."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = MOCK_ASSIGNMENTS

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251", due_after="2026-01-01")

        # Draft Outline has no due date — should be excluded
        assert "Draft Outline" not in result
        # Others with dates should be included
        assert "EDA Notebook" in result

    @pytest.mark.asyncio
    async def test_invalid_due_after_returns_error(self, mock_canvas_api):
        """Invalid date string for due_after returns a clear error."""
        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251", due_after="not-a-date")

        assert "Invalid date format" in result
        assert "due_after" in result
        mock_canvas_api['fetch_all_paginated_results'].assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_due_before_returns_error(self, mock_canvas_api):
        """Invalid date string for due_before returns a clear error."""
        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251", due_before="yesterday")

        assert "Invalid date format" in result
        assert "due_before" in result
        mock_canvas_api['fetch_all_paginated_results'].assert_not_called()

    @pytest.mark.asyncio
    async def test_all_filtered_out_returns_message(self, mock_canvas_api):
        """When all assignments are filtered out, returns a descriptive message."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = MOCK_ASSIGNMENTS

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments(
            "badm_350_120251",
            due_after="2030-01-01",  # Far future — nothing matches
        )

        assert "No assignments found matching filters" in result

    @pytest.mark.asyncio
    async def test_no_filters_returns_all(self, mock_canvas_api):
        """No filters specified returns all assignments."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = MOCK_ASSIGNMENTS

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251")

        assert "EDA Notebook" in result
        assert "Final Report" in result
        assert "Draft Outline" in result
        assert "Midterm Quiz" in result

    # --- Unit 3: include_description payload trimming ---

    @pytest.mark.asyncio
    async def test_include_description_true_default(self, mock_canvas_api):
        """Default include_description=true includes description and rubric."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = MOCK_ASSIGNMENTS

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251")

        assert "Description:" in result
        assert "Explore the dataset" in result
        assert "Rubric:" in result

    @pytest.mark.asyncio
    async def test_include_description_false_strips_fields(self, mock_canvas_api):
        """include_description=false strips description, rubric, and rubric_settings."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = MOCK_ASSIGNMENTS

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251", include_description=False)

        assert "Description:" not in result
        assert "Rubric:" not in result
        assert "Rubric Settings:" not in result
        # Other fields still present
        assert "EDA Notebook" in result
        assert "ID: 101" in result

    @pytest.mark.asyncio
    async def test_include_description_false_shorter_response(self, mock_canvas_api):
        """include_description=false produces a shorter response."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = MOCK_ASSIGNMENTS

        list_assignments = get_tool_function('list_assignments')
        result_with = await list_assignments("badm_350_120251", include_description=True)

        # Reset mock for second call
        mock_canvas_api['fetch_all_paginated_results'].return_value = MOCK_ASSIGNMENTS
        mock_canvas_api['get_course_id'].return_value = "60366"
        mock_canvas_api['get_course_code'].return_value = "badm_350_120251"

        result_without = await list_assignments("badm_350_120251", include_description=False)

        assert len(result_without) < len(result_with)

    @pytest.mark.asyncio
    async def test_include_description_true_no_description(self, mock_canvas_api):
        """include_description=true with empty description produces no Description: line."""
        # Use only the Midterm Quiz which has description=""
        mock_canvas_api['fetch_all_paginated_results'].return_value = [MOCK_ASSIGNMENTS[3]]

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251")

        assert "Midterm Quiz" in result
        assert "Description:" not in result  # Empty description should not appear

    # --- Error handling ---

    @pytest.mark.asyncio
    async def test_api_error_passthrough(self, mock_canvas_api):
        """API errors are returned to the caller."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = {"error": "Rate limited"}

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251")

        assert "Error fetching assignments" in result
        assert "Rate limited" in result

    @pytest.mark.asyncio
    async def test_page_api_error_passthrough(self, mock_canvas_api):
        """API errors when using page param are returned to the caller."""
        mock_canvas_api['make_canvas_request'].return_value = {"error": "Not found"}

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251", page=1)

        assert "Error fetching assignments" in result
        assert "Not found" in result

    @pytest.mark.asyncio
    async def test_empty_course_no_assignments(self, mock_canvas_api):
        """Empty assignment list returns appropriate message."""
        mock_canvas_api['fetch_all_paginated_results'].return_value = []

        list_assignments = get_tool_function('list_assignments')
        result = await list_assignments("badm_350_120251")

        assert "No assignments found" in result


class TestCreateAssignment:
    """Tests for create_assignment tool."""

    @pytest.mark.asyncio
    async def test_create_assignment_basic(self, mock_canvas_api):
        """Test basic assignment creation with minimal parameters."""
        mock_canvas_api['make_canvas_request'].return_value = {
            "id": 12345,
            "name": "Test Assignment",
            "published": False,
            "submission_types": ["none"],
            "html_url": "https://canvas.example.com/courses/60366/assignments/12345"
        }

        create_assignment = get_tool_function('create_assignment')
        assert create_assignment is not None

        result = await create_assignment("badm_350_120251", "Test Assignment")

        # Verify API was called correctly
        mock_canvas_api['get_course_id'].assert_called_once_with("badm_350_120251")
        mock_canvas_api['make_canvas_request'].assert_called_once()

        # Verify the call was a POST with correct data
        call_args = mock_canvas_api['make_canvas_request'].call_args
        assert call_args[0][0] == "post"
        assert "/courses/60366/assignments" in call_args[0][1]
        assert call_args[1]['data']['assignment']['name'] == "Test Assignment"
        assert call_args[1]['data']['assignment']['published'] is False

        # Verify output
        assert "successfully" in result
        assert "Test Assignment" in result
        assert "12345" in result
        assert "Published: No" in result

    @pytest.mark.asyncio
    async def test_create_assignment_with_all_options(self, mock_canvas_api):
        """Test assignment creation with all parameters populated."""
        mock_canvas_api['make_canvas_request'].return_value = {
            "id": 12346,
            "name": "Full Assignment",
            "description": "<p>Test description</p>",
            "published": True,
            "points_possible": 100,
            "due_at": "2026-01-26T23:59:00Z",
            "submission_types": ["online_text_entry", "online_upload"],
            "grading_type": "points",
            "peer_reviews": True,
            "html_url": "https://canvas.example.com/courses/60366/assignments/12346"
        }

        create_assignment = get_tool_function('create_assignment')
        result = await create_assignment(
            "badm_350_120251",
            "Full Assignment",
            description="<p>Test description</p>",
            submission_types="online_text_entry,online_upload",
            due_at="2026-01-26T23:59:00Z",
            points_possible=100,
            grading_type="points",
            published=True,
            peer_reviews=True,
            allowed_extensions="pdf,docx"
        )

        # Verify API call data
        call_args = mock_canvas_api['make_canvas_request'].call_args
        assignment_data = call_args[1]['data']['assignment']

        assert assignment_data['name'] == "Full Assignment"
        assert assignment_data['description'] == "<p>Test description</p>"
        assert assignment_data['submission_types'] == ["online_text_entry", "online_upload"]
        # parse_date converts to isoformat which uses +00:00 instead of Z
        assert assignment_data['due_at'] in ["2026-01-26T23:59:00Z", "2026-01-26T23:59:00+00:00"]
        assert assignment_data['points_possible'] == 100
        assert assignment_data['grading_type'] == "points"
        assert assignment_data['published'] is True
        assert assignment_data['peer_reviews'] is True
        assert assignment_data['allowed_extensions'] == ["pdf", "docx"]

        # Verify output
        assert "successfully" in result
        assert "Full Assignment" in result
        assert "Points: 100" in result
        assert "Published: Yes" in result

    @pytest.mark.asyncio
    async def test_create_assignment_error_handling(self, mock_canvas_api):
        """Test error handling when API fails."""
        mock_canvas_api['make_canvas_request'].return_value = {"error": "Unauthorized"}

        create_assignment = get_tool_function('create_assignment')
        result = await create_assignment("badm_350_120251", "Test Assignment")

        assert "Error" in result
        assert "Unauthorized" in result

    @pytest.mark.asyncio
    async def test_create_assignment_invalid_grading_type(self, mock_canvas_api):
        """Test validation of invalid grading_type."""
        create_assignment = get_tool_function('create_assignment')
        result = await create_assignment(
            "badm_350_120251",
            "Test Assignment",
            grading_type="invalid_type"
        )

        assert "Invalid grading_type" in result
        assert "invalid_type" in result
        # Should not have called the API
        mock_canvas_api['make_canvas_request'].assert_not_called()

    @pytest.mark.asyncio
    async def test_create_assignment_invalid_submission_type(self, mock_canvas_api):
        """Test validation of invalid submission_types."""
        create_assignment = get_tool_function('create_assignment')
        result = await create_assignment(
            "badm_350_120251",
            "Test Assignment",
            submission_types="online_text_entry,invalid_type"
        )

        assert "Invalid submission_type" in result
        assert "invalid_type" in result
        # Should not have called the API
        mock_canvas_api['make_canvas_request'].assert_not_called()

    @pytest.mark.asyncio
    async def test_create_assignment_submission_types_parsing(self, mock_canvas_api):
        """Test that comma-separated submission_types are correctly parsed."""
        mock_canvas_api['make_canvas_request'].return_value = {
            "id": 12347,
            "name": "Multi-Type Assignment",
            "published": False,
            "submission_types": ["online_text_entry", "online_url", "online_upload"]
        }

        create_assignment = get_tool_function('create_assignment')
        _result = await create_assignment(
            "badm_350_120251",
            "Multi-Type Assignment",
            submission_types="online_text_entry, online_url, online_upload"  # Note spaces
        )

        # Verify submission_types were parsed correctly (with whitespace stripped)
        call_args = mock_canvas_api['make_canvas_request'].call_args
        assignment_data = call_args[1]['data']['assignment']
        assert assignment_data['submission_types'] == ["online_text_entry", "online_url", "online_upload"]

    @pytest.mark.asyncio
    async def test_create_assignment_valid_date_parsing(self, mock_canvas_api):
        """Test that valid dates are parsed and formatted correctly."""
        mock_canvas_api['make_canvas_request'].return_value = {
            "id": 12348,
            "name": "Dated Assignment",
            "published": False,
            "due_at": "2026-01-26T23:59:00Z"
        }

        create_assignment = get_tool_function('create_assignment')
        result = await create_assignment(
            "badm_350_120251",
            "Dated Assignment",
            due_at="2026-01-26T23:59:00Z",
            unlock_at="2026-01-20T00:00:00Z",
            lock_at="2026-02-01T23:59:00Z"
        )

        # Verify dates were parsed and sent to API
        call_args = mock_canvas_api['make_canvas_request'].call_args
        assignment_data = call_args[1]['data']['assignment']
        assert "due_at" in assignment_data
        assert "unlock_at" in assignment_data
        assert "lock_at" in assignment_data
        assert "successfully" in result

    @pytest.mark.asyncio
    async def test_create_assignment_invalid_date_format(self, mock_canvas_api):
        """Test validation of invalid date formats."""
        create_assignment = get_tool_function('create_assignment')
        result = await create_assignment(
            "badm_350_120251",
            "Test Assignment",
            due_at="not-a-valid-date"
        )

        assert "Invalid date format" in result
        assert "due_at" in result
        assert "not-a-valid-date" in result
        # Should not have called the API
        mock_canvas_api['make_canvas_request'].assert_not_called()

    @pytest.mark.asyncio
    async def test_create_assignment_invalid_unlock_at_format(self, mock_canvas_api):
        """Test validation of invalid unlock_at date format."""
        create_assignment = get_tool_function('create_assignment')
        result = await create_assignment(
            "badm_350_120251",
            "Test Assignment",
            unlock_at="yesterday"
        )

        assert "Invalid date format" in result
        assert "unlock_at" in result
        # Should not have called the API
        mock_canvas_api['make_canvas_request'].assert_not_called()

    @pytest.mark.asyncio
    async def test_create_assignment_automatic_peer_reviews_without_peer_reviews(self, mock_canvas_api):
        """Test validation that automatic_peer_reviews requires peer_reviews=True."""
        create_assignment = get_tool_function('create_assignment')
        result = await create_assignment(
            "badm_350_120251",
            "Test Assignment",
            automatic_peer_reviews=True,
            peer_reviews=False  # This combination is invalid
        )

        assert "Invalid configuration" in result
        assert "automatic_peer_reviews" in result
        assert "peer_reviews" in result
        # Should not have called the API
        mock_canvas_api['make_canvas_request'].assert_not_called()


class TestUpdateAssignment:
    """Tests for update_assignment tool."""

    @pytest.mark.asyncio
    async def test_update_assignment_basic(self, mock_canvas_api):
        """Test basic assignment update with name change."""
        mock_canvas_api['make_canvas_request'].return_value = {
            "id": 12345,
            "name": "Updated Assignment Name",
            "published": False,
            "submission_types": ["none"],
            "html_url": "https://canvas.example.com/courses/60366/assignments/12345"
        }

        update_assignment = get_tool_function('update_assignment')
        assert update_assignment is not None

        result = await update_assignment("badm_350_120251", 12345, name="Updated Assignment Name")

        # Verify API was called correctly
        mock_canvas_api['get_course_id'].assert_called_once_with("badm_350_120251")
        mock_canvas_api['make_canvas_request'].assert_called_once()

        # Verify the call was a PUT with correct data
        call_args = mock_canvas_api['make_canvas_request'].call_args
        assert call_args[0][0] == "put"
        assert "/courses/60366/assignments/12345" in call_args[0][1]
        assert call_args[1]['data']['assignment']['name'] == "Updated Assignment Name"

        # Verify output
        assert "successfully" in result
        assert "Updated Assignment Name" in result
        assert "Updated fields: name" in result

    @pytest.mark.asyncio
    async def test_update_assignment_multiple_fields(self, mock_canvas_api):
        """Test updating multiple fields at once."""
        mock_canvas_api['make_canvas_request'].return_value = {
            "id": 12345,
            "name": "Updated Name",
            "description": "<p>New description</p>",
            "published": True,
            "points_possible": 150,
            "due_at": "2026-02-15T23:59:00Z",
            "submission_types": ["online_text_entry", "online_upload"],
            "html_url": "https://canvas.example.com/courses/60366/assignments/12345"
        }

        update_assignment = get_tool_function('update_assignment')
        result = await update_assignment(
            "badm_350_120251",
            12345,
            name="Updated Name",
            description="<p>New description</p>",
            points_possible=150,
            due_at="2026-02-15T23:59:00Z",
            published=True
        )

        # Verify API call data
        call_args = mock_canvas_api['make_canvas_request'].call_args
        assignment_data = call_args[1]['data']['assignment']

        assert assignment_data['name'] == "Updated Name"
        assert assignment_data['description'] == "<p>New description</p>"
        assert assignment_data['points_possible'] == 150
        assert assignment_data['published'] is True

        # Verify output includes updated fields
        assert "successfully" in result
        assert "Updated fields:" in result
        assert "name" in result

    @pytest.mark.asyncio
    async def test_update_assignment_no_fields(self, mock_canvas_api):
        """Test that error is returned when no fields are provided."""
        update_assignment = get_tool_function('update_assignment')
        result = await update_assignment("badm_350_120251", 12345)

        assert "No fields provided to update" in result
        # Should not have called the API
        mock_canvas_api['make_canvas_request'].assert_not_called()

    @pytest.mark.asyncio
    async def test_update_assignment_error_handling(self, mock_canvas_api):
        """Test error handling when API fails."""
        mock_canvas_api['make_canvas_request'].return_value = {"error": "Assignment not found"}

        update_assignment = get_tool_function('update_assignment')
        result = await update_assignment("badm_350_120251", 99999, name="New Name")

        assert "Error" in result
        assert "Assignment not found" in result

    @pytest.mark.asyncio
    async def test_update_assignment_invalid_grading_type(self, mock_canvas_api):
        """Test validation of invalid grading_type."""
        update_assignment = get_tool_function('update_assignment')
        result = await update_assignment(
            "badm_350_120251",
            12345,
            grading_type="invalid_type"
        )

        assert "Invalid grading_type" in result
        assert "invalid_type" in result
        # Should not have called the API
        mock_canvas_api['make_canvas_request'].assert_not_called()

    @pytest.mark.asyncio
    async def test_update_assignment_invalid_submission_type(self, mock_canvas_api):
        """Test validation of invalid submission_types."""
        update_assignment = get_tool_function('update_assignment')
        result = await update_assignment(
            "badm_350_120251",
            12345,
            submission_types="online_text_entry,invalid_type"
        )

        assert "Invalid submission_type" in result
        assert "invalid_type" in result
        # Should not have called the API
        mock_canvas_api['make_canvas_request'].assert_not_called()

    @pytest.mark.asyncio
    async def test_update_assignment_invalid_date_format(self, mock_canvas_api):
        """Test validation of invalid date formats."""
        update_assignment = get_tool_function('update_assignment')
        result = await update_assignment(
            "badm_350_120251",
            12345,
            due_at="not-a-valid-date"
        )

        assert "Invalid date format" in result
        assert "due_at" in result
        assert "not-a-valid-date" in result
        # Should not have called the API
        mock_canvas_api['make_canvas_request'].assert_not_called()

    @pytest.mark.asyncio
    async def test_update_assignment_automatic_peer_reviews_without_peer_reviews(self, mock_canvas_api):
        """Test validation that automatic_peer_reviews requires peer_reviews=True."""
        update_assignment = get_tool_function('update_assignment')
        result = await update_assignment(
            "badm_350_120251",
            12345,
            automatic_peer_reviews=True,
            peer_reviews=False  # This combination is invalid
        )

        assert "Invalid configuration" in result
        assert "automatic_peer_reviews" in result
        assert "peer_reviews" in result
        # Should not have called the API
        mock_canvas_api['make_canvas_request'].assert_not_called()

    @pytest.mark.asyncio
    async def test_update_assignment_publish_only(self, mock_canvas_api):
        """Test updating only the published status."""
        mock_canvas_api['make_canvas_request'].return_value = {
            "id": 12345,
            "name": "Test Assignment",
            "published": True,
            "html_url": "https://canvas.example.com/courses/60366/assignments/12345"
        }

        update_assignment = get_tool_function('update_assignment')
        result = await update_assignment("badm_350_120251", 12345, published=True)

        # Verify only published was sent
        call_args = mock_canvas_api['make_canvas_request'].call_args
        assignment_data = call_args[1]['data']['assignment']
        assert assignment_data == {"published": True}

        assert "successfully" in result
        assert "Published: Yes" in result


class TestAssignmentTools:
    """Test assignment tool functions."""

    @pytest.mark.asyncio
    async def test_list_assignments(self):
        """Test listing assignments."""
        mock_assignments = [
            {"id": 1, "name": "Assignment 1", "due_at": "2024-02-15", "points_possible": 100},
            {"id": 2, "name": "Assignment 2", "due_at": "2024-03-01", "points_possible": 50}
        ]

        with patch('canvas_mcp.core.client.fetch_all_paginated_results', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_assignments

            from canvas_mcp.core.client import fetch_all_paginated_results

            result = await fetch_all_paginated_results("/courses/12345/assignments", {})

            assert len(result) == 2
            assert result[0]["name"] == "Assignment 1"

    @pytest.mark.asyncio
    async def test_get_assignment_details(self):
        """Test getting assignment details."""
        mock_assignment = {
            "id": 67890,
            "name": "Test Assignment",
            "description": "Test description",
            "points_possible": 100
        }

        with patch('canvas_mcp.core.client.make_canvas_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_assignment

            from canvas_mcp.core.client import make_canvas_request

            result = await make_canvas_request("get", "/courses/12345/assignments/67890")

            assert result["name"] == "Test Assignment"
            assert result["points_possible"] == 100

    @pytest.mark.asyncio
    async def test_list_submissions(self):
        """Test listing submissions."""
        mock_submissions = [
            {"user_id": 1001, "score": 85, "submitted_at": "2024-02-14"},
            {"user_id": 1002, "score": 92, "submitted_at": "2024-02-14"}
        ]

        with patch('canvas_mcp.core.client.fetch_all_paginated_results', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_submissions

            from canvas_mcp.core.client import fetch_all_paginated_results

            result = await fetch_all_paginated_results("/courses/12345/assignments/67890/submissions", {})

            assert len(result) == 2
            assert result[0]["score"] == 85

    @pytest.mark.asyncio
    async def test_assignment_analytics(self):
        """Test assignment analytics calculation."""
        from statistics import mean, median

        scores = [85, 92, 78, 95, 88]

        avg = mean(scores)
        med = median(scores)

        assert avg == 87.6
        assert med == 88

    @pytest.mark.asyncio
    async def test_empty_submissions(self):
        """Test handling empty submissions list."""
        with patch('canvas_mcp.core.client.fetch_all_paginated_results', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []

            from canvas_mcp.core.client import fetch_all_paginated_results

            result = await fetch_all_paginated_results("/courses/12345/assignments/67890/submissions", {})

            assert result == []

    @pytest.mark.asyncio
    async def test_assignment_error_handling(self):
        """Test error handling in assignment operations."""
        with patch('canvas_mcp.core.client.make_canvas_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"error": "Assignment not found"}

            from canvas_mcp.core.client import make_canvas_request

            result = await make_canvas_request("get", "/courses/12345/assignments/99999")

            assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
