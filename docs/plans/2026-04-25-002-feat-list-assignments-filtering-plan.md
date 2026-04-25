---
title: "feat: Add filtering and pagination to list_assignments"
type: feat
status: active
date: 2026-04-25
---

# feat: Add filtering and pagination to list_assignments

## Overview

Add optional filtering, pagination, and payload-trimming parameters to `list_assignments` so it can handle large courses (150+ assignments) without exceeding the 1MB tool result limit. This removes the need for Claude to fall back to `execute_typescript` for common teacher workflows, which bypasses the FERPA anonymization layer.

## Problem Frame

`list_assignments` currently returns every assignment in a course with full descriptions and rubrics in a single response. For DES 226 (151 assignments), this exceeds the 1MB MCP tool result limit and fails entirely. Claude then falls back to `execute_typescript` raw fetch calls, which bypass the anonymization layer and defeat FERPA compliance. Common workflows like "what's due this week" should be answerable with the typed tool.

## Requirements Trace

- R1. Add `due_after` / `due_before` ISO 8601 date params for client-side date range filtering
- R2. Add `include_description` boolean (default `true`). When `false`, strip `description` and `rubric` fields from response
- R3. Add `published_only` boolean (default `false`). When `true`, exclude unpublished assignments
- R4. Add `per_page` integer (default 100, max 100) and `page` integer (default 1) for manual pagination
- R5. Add `search_term` string param, passed through to Canvas API
- R6. All parameters optional. Default behavior identical to current — no breaking changes
- R7. Update tool description to advertise filtering capabilities so Claude prefers it over `execute_typescript`
- R8. Update AGENTS.md and tools documentation

## Scope Boundaries

- No new `submission_summary` tool
- No modifications to `execute_typescript`
- No changes to `fetch_all_paginated_results` internals
- No restructuring of the response format — only filter what's in it
- Keep this PR focused on `list_assignments` only

### Deferred to Separate Tasks

- Submission summary tool: separate PR
- Similar filtering for other large-payload list tools: future iteration

## Context & Research

### Relevant Code and Patterns

- `src/canvas_mcp/tools/assignments.py:list_assignments` — current implementation (lines 19-73). Single param (`course_identifier`), fetches all with `fetch_all_paginated_results`, includes `all_dates` and `submission`
- `src/canvas_mcp/tools/other_tools.py:list_pages` — best reference for optional filtering pattern (`sort`, `order`, `search_term`, `published`). Conditional param dict building
- `src/canvas_mcp/tools/files.py:list_course_files` — enum validation pattern for sort/order fields
- `src/canvas_mcp/tools/discussions.py:delete_announcements_by_criteria` — client-side date filtering pattern using `parse_date()`
- `src/canvas_mcp/core/dates.py` — `parse_date()` and `format_date()` already imported in assignments.py
- `src/canvas_mcp/core/client.py:fetch_all_paginated_results` — auto-fetches all pages, applies anonymization once at the end

### Institutional Learnings

- Canvas API query params cannot be fully trusted for filtering (per `docs/solutions/api-issues/canvas-enrollment-term-filtering-unreliable.md`). Always post-filter client-side for critical filters. For `published_only`, we should verify client-side even though Canvas may honor it.
- `fetch_all_paginated_results` has no size limit or circuit breaker — it fetches everything into memory. For courses with 150+ assignments, this creates very large response strings.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

| Parameter | Canvas API native? | Implementation |
|-----------|-------------------|----------------|
| `search_term` | Yes | Pass to `params["search_term"]` |
| `per_page` | Yes | Pass to `params["per_page"]`, cap at 100 |
| `page` | Yes | When provided, use single `make_canvas_request` call instead of `fetch_all_paginated_results` |
| `published_only` | No (no native published filter on assignments endpoint) | Client-side: filter out assignments where `published=False` |
| `due_after` | No | Client-side: parse with `parse_date()`, compare `assignment["due_at"]` |
| `due_before` | No | Client-side: parse with `parse_date()`, compare `assignment["due_at"]` |
| `include_description` | No | Client-side: skip `description` and `rubric`/`rubric_settings` fields when formatting response |

**Data flow:**

1. Build Canvas API params (search_term, per_page, include[])
2. Fetch: if `page` is specified, single-page fetch via `make_canvas_request`; otherwise `fetch_all_paginated_results`
3. Client-side filter: `published_only`, `due_after`, `due_before`
4. Format response: conditionally include/exclude `description`, `rubric`, `rubric_settings` based on `include_description`

## Key Technical Decisions

- **Single-page vs all-pages fetch**: When the user passes an explicit `page` param, use `make_canvas_request` directly for a single page. Otherwise continue using `fetch_all_paginated_results` to get all results. This lets users manually paginate large courses without auto-fetching everything.
- **`published_only` is client-side, not `bucket`-based**: Canvas has no native `published` filter on the assignments endpoint. The `bucket` param (`past`, `future`, etc.) is time-based, not publish-state based. Filter client-side after fetch.
- **Strip `rubric` alongside `description`**: When `include_description=false`, also strip `rubric` and `rubric_settings` — these are equally verbose and rarely needed in list views (there's already `list_assignment_rubrics`).
- **Anonymization with single-page fetch**: When using `make_canvas_request` directly (manual pagination), anonymization happens per-call automatically (unlike `fetch_all_paginated_results` which batches it). No special handling needed.

## Open Questions

### Resolved During Planning

- **Should `include_description` default to `true` or `false`?** `true` — preserves backward compatibility. Existing workflows (TD Serendipity Generator, competency mapping) depend on descriptions.
- **What about `bucket` and `order_by`?** The user's spec doesn't include these. They're useful Canvas-native params but out of scope. Can be added in a follow-up.
- **Should date filtering use `parse_date` or manual ISO parsing?** `parse_date` from `core/dates.py` — it's already imported in assignments.py and handles multiple formats gracefully.

### Deferred to Implementation

- Exact wording of the updated tool description (implementer should follow the user's suggested phrasing closely)
- Whether to add a count/total to the response header (e.g., "Showing 12 of 151 assignments") — nice to have but not in spec

## Implementation Units

- [x] **Unit 1: Add parameters and Canvas API pass-through**

  **Goal:** Add all 7 new optional parameters to `list_assignments`, pass Canvas-native ones (`search_term`, `per_page`) to the API, and implement single-page vs all-pages fetch logic

  **Requirements:** R4, R5, R6

  **Dependencies:** None

  **Files:**
  - Modify: `src/canvas_mcp/tools/assignments.py`
  - Test: `tests/tools/test_assignments.py`

  **Approach:**
  - Add parameters to function signature: `due_after`, `due_before`, `include_description`, `published_only`, `per_page`, `page`, `search_term` — all optional with defaults matching current behavior
  - Build params dict conditionally (follow `list_pages` pattern)
  - If `page` is specified: use `make_canvas_request("get", ...)` with `page` and `per_page` in params. Handle anonymization (it's automatic for `make_canvas_request`). Ensure response is wrapped in a list if needed
  - If `page` is not specified: use `fetch_all_paginated_results` as today
  - Validate `per_page` is between 1 and 100

  **Patterns to follow:**
  - `list_pages` in `src/canvas_mcp/tools/other_tools.py` — conditional param building
  - `list_course_files` in `src/canvas_mcp/tools/files.py` — input validation pattern

  **Test scenarios:**
  - Happy path: Call with no new params → behaves identically to current (params dict has `per_page: 100` and `include[]`)
  - Happy path: Call with `search_term="EDA"` → `search_term` appears in params passed to `fetch_all_paginated_results`
  - Happy path: Call with `per_page=50` → `per_page: 50` in params
  - Happy path: Call with `page=2, per_page=25` → uses `make_canvas_request` (not `fetch_all_paginated_results`) with `page: 2, per_page: 25`
  - Edge case: `per_page=0` → returns validation error
  - Edge case: `per_page=200` → capped at 100 or returns validation error

  **Verification:**
  - Tests pass
  - Calling `list_assignments("847")` with no new params produces same API call as before

- [x] **Unit 2: Add client-side filtering (dates, published)**

  **Goal:** Implement `due_after`, `due_before`, and `published_only` client-side filters on the fetched results

  **Requirements:** R1, R3

  **Dependencies:** Unit 1

  **Files:**
  - Modify: `src/canvas_mcp/tools/assignments.py`
  - Test: `tests/tools/test_assignments.py`

  **Approach:**
  - After fetching assignments, apply filters in order: `published_only` first (simple boolean check), then `due_after`/`due_before` (parse dates with `parse_date()`, compare)
  - Assignments with `due_at=None` should be excluded when date filtering is active (they have no due date to compare)
  - Validate date params with `parse_date()` — return error if parsing fails (follow `create_assignment` pattern)

  **Patterns to follow:**
  - `delete_announcements_by_criteria` in `src/canvas_mcp/tools/discussions.py` — client-side date filtering with `parse_date()`
  - `create_assignment` in same file — date validation with `parse_date()`

  **Test scenarios:**
  - Happy path: `due_after="2026-04-18", due_before="2026-04-25"` with mock data containing assignments inside, outside, and on the boundary dates → only matching assignments returned
  - Happy path: `published_only=true` with mix of published/unpublished → only published returned
  - Happy path: Both date and published filters combined → both applied
  - Edge case: `due_after` with assignments that have `due_at=None` → those assignments excluded from results
  - Edge case: Invalid date string for `due_after` → returns clear error message
  - Edge case: All assignments filtered out → returns "No assignments found matching filters" message
  - Happy path: No filters specified → all assignments returned (no filtering applied)

  **Verification:**
  - Tests pass
  - Filtering does not modify the original assignment objects

- [x] **Unit 3: Add `include_description` payload trimming**

  **Goal:** Strip `description`, `rubric`, and `rubric_settings` from response when `include_description=false`

  **Requirements:** R2

  **Dependencies:** Unit 1

  **Files:**
  - Modify: `src/canvas_mcp/tools/assignments.py`
  - Test: `tests/tools/test_assignments.py`

  **Approach:**
  - In the response formatting loop, skip outputting `description`, `rubric`, and `rubric_settings` fields when `include_description=false`
  - This is a formatting-level change — the data is still fetched from Canvas (needed for other filters), just not included in the text output

  **Patterns to follow:**
  - The existing conditional field inclusion pattern in `list_assignments` (lines 57-68): `if description: entry += ...`

  **Test scenarios:**
  - Happy path: `include_description=true` (default) → response includes description and rubric fields (same as today)
  - Happy path: `include_description=false` → response does NOT contain "Description:" or "Rubric:" lines
  - Happy path: `include_description=false` with 3 mock assignments including long descriptions → response is significantly shorter than with descriptions
  - Edge case: `include_description=true` with assignment that has no description → no "Description:" line (existing behavior preserved)

  **Verification:**
  - Tests pass
  - Default behavior unchanged

- [x] **Unit 4: Update tool description and documentation**

  **Goal:** Update the tool docstring, AGENTS.md, and tools docs so Claude prefers this over `execute_typescript`

  **Requirements:** R7, R8

  **Dependencies:** Units 1-3

  **Files:**
  - Modify: `src/canvas_mcp/tools/assignments.py` (docstring)
  - Modify: `AGENTS.md` (tool table entry)
  - Modify: `tools/README.md` (full parameter docs)
  - Modify: `tools/TOOL_MANIFEST.json` (machine-readable catalog)

  **Approach:**
  - Update the tool's docstring to match the user's suggested description, documenting all new parameters and noting that `due_after`/`due_before` are client-side filters
  - Update AGENTS.md tool table entry from "All assignments in a course" to mention filtering capabilities
  - Update tools/README.md with full parameter documentation
  - Update TOOL_MANIFEST.json with new parameters

  **Patterns to follow:**
  - Existing AGENTS.md tool table format
  - Existing tools/README.md parameter documentation style

  **Test expectation:** None — documentation only

  **Verification:**
  - Docstring accurately describes all parameters
  - AGENTS.md entry mentions filtering
  - tools/README.md has full parameter docs

## System-Wide Impact

- **Interaction graph:** `list_assignments` is called by other tools/workflows that scan assignments (TD Serendipity Generator, competency mapping). Default behavior is unchanged, so these continue to work.
- **Error propagation:** Invalid date params return error strings (same pattern as `create_assignment`). Filtered-to-empty results return a descriptive "no assignments found" message.
- **State lifecycle risks:** None — this is a read-only tool. No writes, no caching concerns.
- **API surface parity:** This only changes the MCP tool interface. The Canvas API calls underneath are standard.
- **Unchanged invariants:** Response format is preserved. Default behavior with no new params is identical. `fetch_all_paginated_results` is not modified. Anonymization continues to work through both fetch paths.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Client-side date filtering still requires fetching all pages from Canvas (slow on huge courses) | Document in docstring. Users can combine with `search_term` or `page` to reduce fetch size. Future: add `bucket` param for Canvas-native time filtering |
| Manual pagination (`page` param) bypasses `fetch_all_paginated_results` anonymization batching | `make_canvas_request` applies anonymization per-call automatically. No gap. |
| Canvas API may not reliably honor `search_term` | Per institutional learnings, Canvas API params can be unreliable. `search_term` is best-effort. Document accordingly. |

## Sources & References

- Related code: `src/canvas_mcp/tools/assignments.py:list_assignments`, `src/canvas_mcp/tools/other_tools.py:list_pages`, `src/canvas_mcp/core/client.py:fetch_all_paginated_results`
- Canvas API docs: Assignments endpoint supports `search_term`, `bucket`, `order_by`, `per_page`, `page`
- Institutional learning: `docs/solutions/api-issues/canvas-enrollment-term-filtering-unreliable.md`
