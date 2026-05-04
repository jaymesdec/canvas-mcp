---
title: "feat: Add CANVAS_ALLOW_DELETES guard to block destructive operations"
type: feat
status: active
date: 2026-04-25
origin: docs/brainstorms/2026-04-25-destructive-operation-guards-requirements.md
---

# feat: Add CANVAS_ALLOW_DELETES guard to block destructive operations

## Overview

Add a `CANVAS_ALLOW_DELETES` boolean env var that blocks all HTTP DELETE requests at the `make_canvas_request()` chokepoint. When set to `false`, any DELETE call returns a clear error message instead of reaching Canvas. This protects all 16 current DELETE call sites and any future ones automatically.

## Problem Frame

The MCP server has 13 delete tools plus 3 operations that use HTTP DELETE internally. 8 of these have zero built-in safeguards. A misunderstood agent command could permanently destroy course modules, pages, assignments, or student work. A centralized kill-switch provides a safety floor that complements existing per-tool guards. (see origin: `docs/brainstorms/2026-04-25-destructive-operation-guards-requirements.md`)

## Requirements Trace

- R1. `CANVAS_ALLOW_DELETES=false` blocks all `make_canvas_request(method="delete", ...)` calls before they reach Canvas
- R1. Default is `true` (backward compatible)
- R1. Blocked requests return JSON error dict with endpoint, reason, and remediation
- R1. Blocked attempts logged at WARNING level
- R1. Guard covers all DELETE operations uniformly (including enrollment lifecycle and group membership)
- R1. Case-insensitive method comparison via `.lower()`
- R2. No code changes required (convention only)

## Scope Boundaries

- No full read-only mode (GET-only)
- No per-tool granular permissions
- No exemptions for enrollment or membership DELETE operations
- No modification to existing per-tool dry_run/title-match guards
- No confirmation prompts within the MCP server itself

## Context & Research

### Relevant Code and Patterns

- `src/canvas_mcp/core/config.py` — `_bool_env()` helper (line 17-21), existing boolean fields (lines 45-67)
- `src/canvas_mcp/core/client.py` — `make_canvas_request()` function, DELETE branch at line 175-176
- `src/canvas_mcp/core/logging.py` — `log_warning()` and `sanitize_url()` already imported in client.py
- `tests/security/test_sandbox_defaults.py` — Config default testing pattern using `patch.dict(os.environ, ...)`

### Institutional Learnings

- The `_bool_env()` helper only treats `"true"` (case-insensitive) as True; any other string returns False. New boolean config must use this same helper.
- Config tests live in `tests/security/`, not `tests/core/` (which is empty). Follow this convention.
- The Canvas enrollment term filtering solution (`docs/solutions/api-issues/`) established the precedent for client-side defensive guards in this codebase.

## Key Technical Decisions

- **Guard placement: before the retry loop (line 136), not inside the method dispatch**: Short-circuits immediately without entering the retry/rate-limit loop. The guard only needs config + method + endpoint, all available at line 134.
- **Test location: `tests/security/test_delete_guard.py`**: Follows the existing convention where config-level security tests live in `tests/security/`, not `tests/core/`.
- **Error return format: `{"error": "..."}`**: Matches the established error return pattern in `make_canvas_request()` (see lines 177-178, 228-229 of client.py). Tools already handle this format.

## Open Questions

### Resolved During Planning

- **Should the guard go before or inside the retry loop?** Before — no reason to enter the retry loop for a blocked request. The config, method, and endpoint are all available before line 136.
- **Should we also call `log_data_access()` for blocked requests?** No — `log_data_access` is imported inside the try block (line 193) and is meant for actual API interactions. `log_warning()` with the endpoint is sufficient for the audit trail.

### Deferred to Implementation

- Exact wording of the error message (implementer should make it clear and match the style of existing error returns)

## Implementation Units

- [ ] **Unit 1: Add config field**

  **Goal:** Register `CANVAS_ALLOW_DELETES` in the Config class

  **Requirements:** R1 (env var with default `true`)

  **Dependencies:** None

  **Files:**
  - Modify: `src/canvas_mcp/core/config.py`
  - Test: `tests/security/test_delete_guard.py`

  **Approach:**
  - Add `self.allow_deletes = _bool_env("CANVAS_ALLOW_DELETES", True)` to `Config.__init__()`, in the "Privacy and security configuration" section (after line 57, near the other security-related booleans)

  **Patterns to follow:**
  - `self.log_redact_pii = _bool_env("LOG_REDACT_PII", True)` — same helper, same section, boolean defaulting to True

  **Test scenarios:**
  - Happy path: Config defaults to `allow_deletes=True` when env var is not set
  - Happy path: Config sets `allow_deletes=True` when `CANVAS_ALLOW_DELETES=true`
  - Happy path: Config sets `allow_deletes=False` when `CANVAS_ALLOW_DELETES=false`
  - Edge case: Config sets `allow_deletes=False` when `CANVAS_ALLOW_DELETES=FALSE` (case insensitive)
  - Edge case: Config sets `allow_deletes=False` when `CANVAS_ALLOW_DELETES=yes` (only "true" is truthy per `_bool_env`)

  **Verification:**
  - `pytest tests/security/test_delete_guard.py` passes
  - Config field accessible via `get_config().allow_deletes`

- [ ] **Unit 2: Add delete guard in client**

  **Goal:** Block DELETE requests when `allow_deletes` is False

  **Requirements:** R1 (block at chokepoint, error message, WARNING log)

  **Dependencies:** Unit 1

  **Files:**
  - Modify: `src/canvas_mcp/core/client.py`
  - Test: `tests/security/test_delete_guard.py`

  **Approach:**
  - Insert guard between URL construction (line 134) and the retry loop (line 136-137)
  - Check `method.lower() == "delete" and not config.allow_deletes`
  - Call `log_warning()` with the sanitized endpoint
  - Return `{"error": "..."}` with what was blocked, why, and how to enable
  - The guard is ~5 lines of code

  **Patterns to follow:**
  - Error return: `return {"error": f"Unsupported method: {method}"}` (line 178 of client.py)
  - Logging: `log_warning()` already imported (line 8 of client.py)
  - URL sanitization: `sanitize_url()` already imported and used in the function

  **Test scenarios:**
  - Happy path: DELETE request passes through when `allow_deletes=True` (default) — verify the httpx client's `.delete()` method is called
  - Happy path: DELETE request blocked when `allow_deletes=False` — verify error dict returned with "error" key
  - Happy path: Error message includes the endpoint path so the user knows what was blocked
  - Happy path: Error message includes remediation instructions (mentions `CANVAS_ALLOW_DELETES`)
  - Happy path: GET/POST/PUT requests unaffected when `allow_deletes=False` — verify they pass through normally
  - Edge case: DELETE with uppercase method string `"DELETE"` is also blocked (case-insensitive check)
  - Integration: `log_warning()` is called when a DELETE is blocked
  - Integration: httpx client `.delete()` is never called when guard blocks the request

  **Verification:**
  - `pytest tests/security/test_delete_guard.py` passes
  - Manual test: set `CANVAS_ALLOW_DELETES=false` in `.env`, call any delete tool, observe the error message

- [ ] **Unit 3: Document the env var**

  **Goal:** Add `CANVAS_ALLOW_DELETES` to AGENTS.md and CLAUDE.md so users and agents know about it

  **Requirements:** R1 (documentation)

  **Dependencies:** Units 1-2

  **Files:**
  - Modify: `AGENTS.md` (add to constraints/configuration section)
  - Modify: `CLAUDE.md` (add to Environment Setup or a new Safety section)

  **Approach:**
  - Add a brief note about the env var, its default, and its effect
  - Keep it concise — one bullet or a small table row

  **Patterns to follow:**
  - Existing env var documentation style in CLAUDE.md and AGENTS.md

  **Test expectation:** None — documentation only

  **Verification:**
  - Env var is mentioned in both AGENTS.md and CLAUDE.md
  - Description matches the actual behavior

## System-Wide Impact

- **Interaction graph:** The guard sits at the single chokepoint (`make_canvas_request`) that all 16 DELETE call sites flow through. No callbacks, middleware, or observers affected.
- **Error propagation:** Blocked requests return `{"error": "..."}` — the same format tools already handle for Canvas API errors. Each tool's error handling will naturally propagate this to the user.
- **State lifecycle risks:** None — the guard blocks before any state change occurs.
- **API surface parity:** All DELETE operations are uniformly blocked. No surface is missed.
- **Unchanged invariants:** GET, POST, PUT requests are completely unaffected. Existing per-tool dry_run and title-match guards remain in place as a complementary layer.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Enrollment lifecycle operations blocked when deletes disabled | Documented as intentional in requirements. Toggle the env var when needed. |
| User forgets the env var exists and can't delete | Error message explicitly says how to re-enable |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-25-destructive-operation-guards-requirements.md](docs/brainstorms/2026-04-25-destructive-operation-guards-requirements.md)
- Related code: `src/canvas_mcp/core/client.py:make_canvas_request()`, `src/canvas_mcp/core/config.py:Config`
- Related pattern: `tests/security/test_sandbox_defaults.py` (config default testing)
