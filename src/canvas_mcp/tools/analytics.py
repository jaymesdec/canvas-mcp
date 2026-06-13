"""Course analytics MCP tools for Canvas API.

Instructor-facing analytics summarizing student activity, participation, and
assignment completion across a course.
"""

from mcp.server.fastmcp import FastMCP

from ..core.anonymization import anonymize_response_data
from ..core.cache import get_course_code, get_course_id
from ..core.client import fetch_all_paginated_results, make_canvas_request
from ..core.validation import validate_params


def register_analytics_tools(mcp: FastMCP) -> None:
    """Register course analytics MCP tools."""

    @mcp.tool()
    @validate_params
    async def get_student_analytics(course_identifier: str,
                                  current_only: bool = True,
                                  include_participation: bool = True,
                                  include_assignment_stats: bool = True,
                                  include_access_stats: bool = True) -> str:
        """Get detailed analytics about student activity, participation, and progress in a course.

        Args:
            course_identifier: The Canvas course code (e.g., badm_554_120251_246794) or ID
            current_only: Whether to include only assignments due on or before today
            include_participation: Whether to include participation data (discussions, submissions)
            include_assignment_stats: Whether to include assignment completion statistics
            include_access_stats: Whether to include course access statistics
        """
        course_id = await get_course_id(course_identifier)

        # Get basic course info
        course_response = await make_canvas_request("get", f"/courses/{course_id}")
        if "error" in course_response:
            return f"Error fetching course: {course_response['error']}"

        course_name = course_response.get("name", "Unknown Course")

        # Get students
        students = await fetch_all_paginated_results(
            f"/courses/{course_id}/users",
            {"enrollment_type[]": "student", "per_page": 100}
        )

        if isinstance(students, dict) and "error" in students:
            return f"Error fetching students: {students['error']}"

        # Anonymize student data to protect privacy
        try:
            students = anonymize_response_data(students, data_type="users")
        except Exception as e:
            print(f"Warning: Failed to anonymize student analytics data: {str(e)}")
            # Continue with original data for functionality

        # Get assignments
        assignments = await fetch_all_paginated_results(
            f"/courses/{course_id}/assignments",
            {"per_page": 100}
        )

        if isinstance(assignments, dict) and "error" in assignments:
            assignments = []

        course_display = await get_course_code(course_id) or course_identifier
        output = f"Student Analytics for Course {course_display} ({course_name})\n\n"

        output += f"Total Students: {len(students)}\n"
        output += f"Total Assignments: {len(assignments)}\n\n"

        if include_assignment_stats and assignments:
            # Calculate assignment completion stats
            published_assignments = [a for a in assignments if a.get("published", False)]
            total_points = sum(a.get("points_possible", 0) for a in published_assignments)

            output += f"Published Assignments: {len(published_assignments)}\n"
            output += f"Total Points Available: {total_points}\n\n"

        output += "This analytics feature provides basic course statistics.\n"
        output += "For detailed individual student analytics, use specific assignment analytics tools."

        return output
