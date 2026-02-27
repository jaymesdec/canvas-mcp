# Franklin Sandbox IMSCC Import (MVP)

This repo now includes a Canvas MCP tool to import a local `.imscc` package into a **newly-created Canvas course**.

## Tool

`import_imscc_to_new_course(local_imscc_path: str, course_name: str, account_id: int, term_id: Optional[int] = None, publish: bool = False) -> str`

## What it does

1. Validates local file exists and is `.imscc`
2. Creates a new destination course in the provided account/subaccount
3. Creates a `common_cartridge_importer` content migration using pre-attachment upload flow
4. Uploads the local `.imscc` to Canvas storage URL
5. Polls migration until terminal status (`completed` or `failed`)
6. Returns migration status + progress endpoints, current status/progress, and migration issues endpoint
7. Optionally publishes the destination course (`publish=True`)

## Required Franklin sandbox config

Set these values before running the MCP server:

- `CANVAS_API_URL` - Franklin sandbox Canvas base URL (example: `https://franklin.instructure.com`)
- `CANVAS_API_TOKEN` - API token for a user with permissions to:
  - create courses in target account/subaccount
  - create content migrations in those courses
- (Optional) `DEFAULT_TERM_ID` - default term if you want consistent term behavior elsewhere in tools

## Example test call

```json
{
  "tool": "import_imscc_to_new_course",
  "arguments": {
    "local_imscc_path": "/Users/jdec/Downloads/algebra-template.imscc",
    "course_name": "Algebra I - Imported Template",
    "account_id": 42,
    "term_id": 155,
    "publish": false
  }
}
```

## Notes

- If auth is invalid, tool returns an explicit 401 guidance message.
- If token lacks privileges, tool returns an explicit 403 permission guidance message.
- Migration issues can be queried with the returned `Migration Issues Endpoint`.
