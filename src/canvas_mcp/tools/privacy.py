"""Privacy and anonymization MCP tools for Canvas API.

Tools for inspecting the data-anonymization status and generating local
de-anonymization maps so faculty can recover real identities from anonymous IDs.
"""

from mcp.server.fastmcp import FastMCP

from ..core.cache import get_course_code, get_course_id
from ..core.client import fetch_all_paginated_results
from ..core.validation import validate_params


def register_privacy_tools(mcp: FastMCP) -> None:
    """Register privacy and anonymization MCP tools."""

    @mcp.tool()
    async def get_anonymization_status() -> str:
        """Get current data anonymization status and statistics.

        Returns:
            Status information about data anonymization
        """
        from ..core.anonymization import get_anonymization_stats
        from ..core.config import get_config

        config = get_config()
        stats = get_anonymization_stats()

        result = "🔒 Data Anonymization Status:\n\n"

        if config.enable_data_anonymization:
            result += "✅ **ANONYMIZATION ENABLED** - Student data is protected\n\n"
            result += "📊 Session Statistics:\n"
            result += f"  • Total unique students anonymized: {stats['total_anonymized_ids']}\n"
            result += f"  • Privacy protection: {stats['privacy_status']}\n"
            result += f"  • Debug logging: {'ON' if config.anonymization_debug else 'OFF'}\n\n"

            if stats['total_anonymized_ids'] > 0:
                result += "🎭 Anonymous ID Examples:\n"
                for i, (real_hint, anon_id) in enumerate(stats['sample_mappings'].items()):
                    result += f"  • {real_hint} → {anon_id}\n"
                    if i >= 2:  # Limit to 3 examples
                        break
                result += "\n"

            result += "🛡️ **FERPA Compliance**: Data anonymized before AI processing\n"
            result += "📍 **Data Location**: All processing happens locally on your machine\n"

        else:
            result += "⚠️ **ANONYMIZATION DISABLED** - Student data is NOT protected\n\n"
            result += "🚨 **PRIVACY RISK**: Real student names and data sent to AI\n"
            result += "⚖️ **COMPLIANCE**: May violate FERPA requirements\n\n"
            result += "💡 **Recommendation**: Enable anonymization in your .env file:\n"
            result += "   ENABLE_DATA_ANONYMIZATION=true\n"

        return result

    @mcp.tool()
    @validate_params
    async def create_student_anonymization_map(course_identifier: str | int) -> str:
        """Create a local CSV file mapping real student data to anonymous IDs for a course.

        This tool generates a de-anonymization key that allows faculty to identify students
        from their anonymous IDs. The file is saved locally and should be kept secure.

        Args:
            course_identifier: The Canvas course code (e.g., badm_554_120251_246794) or ID
        """
        import csv
        from pathlib import Path

        from ..core.anonymization import generate_anonymous_id

        course_id = await get_course_id(course_identifier)

        # Get all students in the course
        params = {
            "enrollment_type[]": "student",
            "include[]": ["email"],
            "per_page": 100
        }

        students = await fetch_all_paginated_results(
            f"/courses/{course_id}/users", params
        )

        if isinstance(students, dict) and "error" in students:
            return f"Error fetching students: {students['error']}"

        if not students:
            return f"No students found for course {course_identifier}."

        # Create local_maps directory if it doesn't exist
        maps_dir = Path("local_maps")
        maps_dir.mkdir(exist_ok=True)

        # Generate filename with course identifier
        course_display = await get_course_code(course_id) or str(course_identifier)
        safe_course_name = "".join(c for c in course_display if c.isalnum() or c in ("-", "_"))
        filename = f"anonymization_map_{safe_course_name}.csv"
        filepath = maps_dir / filename

        # Create mapping data
        mapping_data = []
        for student in students:
            real_id = student.get("id")
            real_name = student.get("name", "Unknown")
            real_email = student.get("email", "No email")

            # Generate the same anonymous ID that would be used by the anonymization system
            anonymous_id = generate_anonymous_id(real_id, prefix="Student")

            mapping_data.append({
                "real_name": real_name,
                "real_id": real_id,
                "real_email": real_email,
                "anonymous_id": anonymous_id
            })

        # Write to CSV file
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ["real_name", "real_id", "real_email", "anonymous_id"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                writer.writerows(mapping_data)

            result = "✅ Student anonymization map created successfully!\n\n"
            result += f"📁 File location: {filepath}\n"
            result += f"👥 Students mapped: {len(mapping_data)}\n"
            result += f"🏫 Course: {course_display}\n\n"
            result += "⚠️ **SECURITY WARNING:**\n"
            result += "This file contains sensitive student information and should be:\n"
            result += "• Kept secure and not shared\n"
            result += "• Deleted when no longer needed\n"
            result += "• Never committed to version control\n\n"
            result += "📋 File format: CSV with columns real_name, real_id, real_email, anonymous_id\n"
            result += "🔍 Use this file to identify students from their anonymous IDs in tool outputs."

            return result

        except Exception as e:
            return f"Error creating anonymization map: {str(e)}"
