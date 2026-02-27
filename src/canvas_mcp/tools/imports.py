"""Content import MCP tools for Canvas API."""

import asyncio
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..core.client import make_canvas_request, upload_file_to_storage
from ..core.validation import validate_params


def _parse_canvas_error(error_text: str) -> str:
    """Return clearer error guidance for common Canvas auth/permission failures."""
    lower = error_text.lower()

    if "401" in lower:
        return (
            "Authentication failed (401). Check CANVAS_API_TOKEN and confirm it is active "
            "for your Franklin sandbox user."
        )

    if "403" in lower:
        return (
            "Permission denied (403). Your token likely lacks account-level rights to "
            "create courses/content migrations in this account/subaccount."
        )

    if "404" in lower:
        return (
            "Resource not found (404). Verify account_id, course_id, and your sandbox "
            "base URL are correct."
        )

    return error_text


async def _poll_migration_status(course_id: int, migration_id: int, timeout_seconds: int = 600) -> dict[str, Any]:
    """Poll content migration status until terminal state or timeout."""
    elapsed = 0
    interval = 5

    while elapsed <= timeout_seconds:
        migration = await make_canvas_request(
            "get",
            f"/courses/{course_id}/content_migrations/{migration_id}",
            params={"include[]": "migration_issues"}
        )

        if isinstance(migration, dict) and "error" in migration:
            return {"error": _parse_canvas_error(migration["error"])}

        state = migration.get("workflow_state", "unknown")
        if state in {"completed", "failed"}:
            return migration

        await asyncio.sleep(interval)
        elapsed += interval

    return {"error": f"Timed out waiting for migration {migration_id} after {timeout_seconds} seconds."}


def register_import_tools(mcp: FastMCP):
    """Register import-related MCP tools."""

    @mcp.tool()
    @validate_params
    async def import_imscc_to_new_course(
        local_imscc_path: str,
        course_name: str,
        account_id: int,
        term_id: int | None = None,
        publish: bool = False,
    ) -> str:
        """Create a new Canvas course and import an IMSCC package from a local file.

        Workflow:
        1) Validate local IMSCC path and extension
        2) Create destination course in account/subaccount
        3) Create content migration using common_cartridge_importer + pre_attachment
        4) Upload IMSCC file to returned storage URL
        5) Poll migration status until completed/failed
        6) Optionally publish the new course

        Args:
            local_imscc_path: Absolute or relative path to .imscc file on local filesystem
            course_name: Name for the newly created course
            account_id: Canvas account or subaccount ID where course will be created
            term_id: Optional enrollment term ID
            publish: If True, publish (offer) the course after import succeeds
        """
        imscc_path = Path(local_imscc_path).expanduser().resolve()

        if not imscc_path.exists() or not imscc_path.is_file():
            return f"❌ IMSCC file not found: {imscc_path}"

        if imscc_path.suffix.lower() != ".imscc":
            return (
                f"❌ Invalid file extension for '{imscc_path.name}'. "
                "Expected a .imscc file."
            )

        try:
            file_size = imscc_path.stat().st_size
        except OSError as e:
            return f"❌ Failed to read IMSCC file metadata: {e}"

        if file_size <= 0:
            return "❌ IMSCC file is empty."

        # Step 1: Create destination course
        create_course_data: dict[str, Any] = {
            "course[name]": course_name,
        }
        if term_id is not None:
            create_course_data["course[term_id]"] = term_id

        created_course = await make_canvas_request(
            "post",
            f"/accounts/{account_id}/courses",
            data=create_course_data,
            use_form_data=True,
        )

        if isinstance(created_course, dict) and "error" in created_course:
            return f"❌ Failed to create destination course: {_parse_canvas_error(created_course['error'])}"

        course_id = created_course.get("id")
        if not course_id:
            return f"❌ Course creation response missing course ID: {created_course}"

        # Step 2: Create migration with pre_attachment workflow
        migration_data = {
            "migration_type": "common_cartridge_importer",
            "pre_attachment[name]": imscc_path.name,
            "pre_attachment[size]": file_size,
            "settings[file_url]": "",
        }

        migration = await make_canvas_request(
            "post",
            f"/courses/{course_id}/content_migrations",
            data=migration_data,
            use_form_data=True,
        )

        if isinstance(migration, dict) and "error" in migration:
            return f"❌ Failed to create content migration: {_parse_canvas_error(migration['error'])}"

        migration_id = migration.get("id")
        if not migration_id:
            return f"❌ Migration creation response missing migration ID: {migration}"

        pre_attachment = migration.get("pre_attachment", {}) if isinstance(migration, dict) else {}
        upload_url = pre_attachment.get("upload_url")
        upload_params = pre_attachment.get("upload_params", {})

        if not upload_url:
            return (
                "❌ Migration created but no pre_attachment upload URL was returned. "
                "Check Canvas permissions and content migration settings."
            )

        # Step 3: Upload IMSCC package
        upload_result = await upload_file_to_storage(
            upload_url=upload_url,
            upload_params=upload_params,
            file_path=str(imscc_path),
            filename=imscc_path.name,
            content_type="application/octet-stream",
        )

        if isinstance(upload_result, dict) and "error" in upload_result:
            details = upload_result.get("details", "")
            detail_text = f" Details: {details}" if details else ""
            return f"❌ IMSCC upload failed: {upload_result['error']}{detail_text}"

        # Step 4: Poll status
        final_migration = await _poll_migration_status(course_id=int(course_id), migration_id=int(migration_id))
        if isinstance(final_migration, dict) and "error" in final_migration:
            return f"❌ Migration polling failed: {final_migration['error']}"

        final_state = final_migration.get("workflow_state", "unknown")
        progress = final_migration.get("progress", 0)
        status_url = final_migration.get("url") or f"/api/v1/courses/{course_id}/content_migrations/{migration_id}"
        progress_url = final_migration.get("progress_url") or status_url
        issues_url = final_migration.get("migration_issues_url") or f"/api/v1/courses/{course_id}/content_migrations/{migration_id}/migration_issues"

        # Optional publish
        publish_note = "No"
        if publish and final_state == "completed":
            publish_response = await make_canvas_request(
                "put",
                f"/courses/{course_id}",
                data={"course[event]": "offer"},
                use_form_data=True,
            )
            if isinstance(publish_response, dict) and "error" in publish_response:
                publish_note = f"Attempted, but failed: {_parse_canvas_error(publish_response['error'])}"
            else:
                publish_note = "Yes"

        status_icon = "✅" if final_state == "completed" else "⚠️"
        return (
            f"{status_icon} IMSCC import finished for new course.\n\n"
            f"Course ID: {course_id}\n"
            f"Course Name: {created_course.get('name', course_name)}\n"
            f"Migration ID: {migration_id}\n"
            f"Workflow State: {final_state}\n"
            f"Progress: {progress}%\n"
            f"Migration Status Endpoint: {status_url}\n"
            f"Migration Progress Endpoint: {progress_url}\n"
            f"Migration Issues Endpoint: {issues_url}\n"
            f"Published: {publish_note}"
        )
