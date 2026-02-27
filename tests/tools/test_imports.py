"""Tests for IMSCC import tools."""

from unittest.mock import patch

import pytest


@pytest.fixture
def mock_import_api():
    with patch('canvas_mcp.tools.imports.make_canvas_request') as mock_request, \
         patch('canvas_mcp.tools.imports.upload_file_to_storage') as mock_upload, \
         patch('canvas_mcp.tools.imports.asyncio.sleep') as mock_sleep:
        yield {
            'make_canvas_request': mock_request,
            'upload_file_to_storage': mock_upload,
            'sleep': mock_sleep,
        }


def get_tool_function(tool_name: str):
    from mcp.server.fastmcp import FastMCP
    from canvas_mcp.tools.imports import register_import_tools

    mcp = FastMCP("test")
    captured_functions = {}

    original_tool = mcp.tool

    def capturing_tool(*args, **kwargs):
        decorator = original_tool(*args, **kwargs)

        def wrapper(fn):
            captured_functions[fn.__name__] = fn
            return decorator(fn)

        return wrapper

    mcp.tool = capturing_tool
    register_import_tools(mcp)
    return captured_functions.get(tool_name)


class TestImportImsccToNewCourse:
    @pytest.mark.asyncio
    async def test_missing_file_validation(self):
        tool = get_tool_function('import_imscc_to_new_course')
        result = await tool(
            local_imscc_path='/does/not/exist/file.imscc',
            course_name='Imported Course',
            account_id=1,
        )
        assert 'not found' in result.lower()

    @pytest.mark.asyncio
    async def test_extension_validation(self, tmp_path):
        bad_file = tmp_path / 'not-imscc.zip'
        bad_file.write_bytes(b'test')

        tool = get_tool_function('import_imscc_to_new_course')
        result = await tool(
            local_imscc_path=str(bad_file),
            course_name='Imported Course',
            account_id=1,
        )
        assert 'expected a .imscc' in result.lower()

    @pytest.mark.asyncio
    async def test_happy_path(self, mock_import_api, tmp_path):
        imscc = tmp_path / 'course.imscc'
        imscc.write_bytes(b'imscc-content')

        # create course, create migration, poll(in-progress), poll(done), publish
        mock_import_api['make_canvas_request'].side_effect = [
            {'id': 9001, 'name': 'My New Course'},
            {
                'id': 7001,
                'pre_attachment': {
                    'upload_url': 'https://upload.example.com',
                    'upload_params': {'key': 'abc'},
                },
            },
            {'id': 7001, 'workflow_state': 'running', 'progress': 35},
            {'id': 7001, 'workflow_state': 'completed', 'progress': 100, 'migration_issues_url': '/issues'},
            {'id': 9001, 'workflow_state': 'available'},
        ]
        mock_import_api['upload_file_to_storage'].return_value = {'success': True}

        tool = get_tool_function('import_imscc_to_new_course')
        result = await tool(
            local_imscc_path=str(imscc),
            course_name='My New Course',
            account_id=55,
            term_id=155,
            publish=True,
        )

        assert '✅' in result
        assert 'Course ID: 9001' in result
        assert 'Migration ID: 7001' in result
        assert 'Progress: 100%' in result
        assert 'Published: Yes' in result

    @pytest.mark.asyncio
    async def test_auth_error_message(self, mock_import_api, tmp_path):
        imscc = tmp_path / 'course.imscc'
        imscc.write_bytes(b'imscc-content')

        mock_import_api['make_canvas_request'].return_value = {
            'error': 'HTTP error: 403, Details: forbidden'
        }

        tool = get_tool_function('import_imscc_to_new_course')
        result = await tool(
            local_imscc_path=str(imscc),
            course_name='Denied Course',
            account_id=99,
        )

        assert 'permission denied' in result.lower()
