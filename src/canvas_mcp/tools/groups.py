"""Canvas group management tools."""

from mcp.server.fastmcp import FastMCP

from ..core.anonymization import anonymize_response_data
from ..core.cache import get_course_code, get_course_id
from ..core.client import fetch_all_paginated_results, make_canvas_request
from ..core.logging import log_info
from ..core.validation import validate_params


def register_group_tools(mcp: FastMCP) -> None:
    """Register Canvas group management tools."""

    @mcp.tool()
    @validate_params
    async def create_group_category(
        course_identifier: str | int,
        name: str,
        self_signup: str | None = None,
        group_limit: int | None = None
    ) -> str:
        """Create a group category (set) in a course.

        Group categories organize groups. Students are assigned to groups within a category.

        Args:
            course_identifier: The Canvas course code or ID
            name: Name for the group category (e.g., "Project Teams", "Lab Groups")
            self_signup: Self-signup mode: "enabled" (students pick), "restricted" (pick within section), or None (manual)
            group_limit: Maximum number of students per group (None for unlimited)
        """
        course_id = await get_course_id(course_identifier)

        data = {"name": name}
        if self_signup is not None:
            data["self_signup"] = self_signup
        if group_limit is not None:
            data["group_limit"] = group_limit

        response = await make_canvas_request(
            "post",
            f"/courses/{course_id}/group_categories",
            data=data
        )

        if isinstance(response, dict) and "error" in response:
            return f"Error creating group category: {response['error']}"

        category_id = response.get("id")
        category_name = response.get("name", name)

        course_display = await get_course_code(course_id) or course_identifier
        result = f"Group category created successfully in course {course_display}!\n\n"
        result += f"Category ID: {category_id}\n"
        result += f"Name: {category_name}\n"
        if self_signup:
            result += f"Self-signup: {self_signup}\n"
        if group_limit:
            result += f"Group limit: {group_limit} students\n"
        return result

    @mcp.tool()
    @validate_params
    async def create_group(
        group_category_id: str | int,
        name: str
    ) -> str:
        """Create a group within a group category.

        Args:
            group_category_id: The group category ID (from create_group_category)
            name: Name for the group (e.g., "Team Alpha", "Lab Group 1")
        """
        data = {"name": name}

        response = await make_canvas_request(
            "post",
            f"/group_categories/{group_category_id}/groups",
            data=data
        )

        if isinstance(response, dict) and "error" in response:
            return f"Error creating group: {response['error']}"

        group_id = response.get("id")
        group_name = response.get("name", name)

        result = "Group created successfully!\n\n"
        result += f"Group ID: {group_id}\n"
        result += f"Name: {group_name}\n"
        result += f"Category ID: {group_category_id}\n"
        return result

    @mcp.tool()
    @validate_params
    async def update_group_membership(
        group_id: str | int,
        user_ids: list[str | int]
    ) -> str:
        """Set members of a group (replaces existing membership).

        Adds specified users to the group. Existing members not in the list
        are removed from the group.

        Args:
            group_id: The Canvas group ID
            user_ids: List of Canvas user IDs to set as group members
        """
        if not user_ids:
            return "Error: user_ids cannot be empty"

        # First, get current memberships to remove them
        current_memberships = await make_canvas_request(
            "get",
            f"/groups/{group_id}/memberships",
            params={"per_page": 100}
        )

        # Remove existing members
        if isinstance(current_memberships, list):
            for membership in current_memberships:
                membership_id = membership.get("id")
                if membership_id:
                    await make_canvas_request(
                        "delete",
                        f"/groups/{group_id}/memberships/{membership_id}"
                    )

        # Add new members
        added = []
        failed = []
        for user_id in user_ids:
            response = await make_canvas_request(
                "post",
                f"/groups/{group_id}/memberships",
                data={"user_id": str(user_id)}
            )
            if isinstance(response, dict) and "error" in response:
                failed.append({"user_id": str(user_id), "error": response["error"]})
            else:
                added.append(str(user_id))

        result = f"Group {group_id} membership updated!\n\n"
        result += f"Members added: {len(added)}\n"
        if failed:
            result += f"Failed to add: {len(failed)}\n"
            for failure in failed:
                result += f"  - User {failure['user_id']}: {failure['error']}\n"

        return result

    @mcp.tool()
    @validate_params
    async def delete_group(group_id: str | int) -> str:
        """Delete a group.

        Args:
            group_id: The Canvas group ID to delete
        """
        # Get group details first for confirmation
        group_details = await make_canvas_request("get", f"/groups/{group_id}")
        group_name = "Unknown"
        if isinstance(group_details, dict) and "error" not in group_details:
            group_name = group_details.get("name", "Unknown")

        response = await make_canvas_request("delete", f"/groups/{group_id}")

        if isinstance(response, dict) and "error" in response:
            return f"Error deleting group: {response['error']}"

        result = "Group deleted successfully!\n\n"
        result += f"Group ID: {group_id}\n"
        result += f"Name: {group_name}\n"
        return result

    @mcp.tool()
    @validate_params
    async def list_groups(course_identifier: str | int) -> str:
        """List all groups and their members for a specific course.

        Args:
            course_identifier: The Canvas course code (e.g., badm_554_120251_246794) or ID
        """
        course_id = await get_course_id(course_identifier)

        # Get all groups in the course
        groups = await fetch_all_paginated_results(
            f"/courses/{course_id}/groups", {"per_page": 100}
        )

        if isinstance(groups, dict) and "error" in groups:
            return f"Error fetching groups: {groups['error']}"

        if not groups:
            return f"No groups found for course {course_identifier}."

        # Format the output
        course_display = await get_course_code(course_id) or course_identifier
        output = f"Groups for Course {course_display}:\n\n"

        for group in groups:
            group_id = group.get("id")
            group_name = group.get("name", "Unnamed group")
            group_category = group.get("group_category_id", "Uncategorized")
            member_count = group.get("members_count", 0)

            output += f"Group: {group_name}\n"
            output += f"ID: {group_id}\n"
            output += f"Category ID: {group_category}\n"
            output += f"Member Count: {member_count}\n"

            # Get members for this group
            members = await fetch_all_paginated_results(
                f"/groups/{group_id}/users", {"per_page": 100}
            )

            if isinstance(members, dict) and "error" in members:
                output += f"Error fetching members: {members['error']}\n"
            elif not members:
                output += "No members in this group.\n"
            else:
                # Anonymize member data to protect student privacy
                try:
                    members = anonymize_response_data(members, data_type="users")
                except Exception as e:
                    print(f"Warning: Failed to anonymize group member data: {str(e)}")
                    # Continue with original data for functionality
                output += "Members:\n"
                for member in members:
                    member_id = member.get("id")
                    member_name = member.get("name", "Unnamed user")
                    member_email = member.get("email", "No email")
                    output += f"  - {member_name} (ID: {member_id}, Email: {member_email})\n"

            output += "\n"

        return output

    log_info("Canvas group tools registered successfully!")
