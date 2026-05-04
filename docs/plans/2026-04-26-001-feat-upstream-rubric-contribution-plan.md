---
title: "feat: Contribute rubric creation tools to upstream canvas-mcp"
type: feat
status: active
date: 2026-04-26
---

# Contribute Rubric Creation Tools to Upstream canvas-mcp

## Overview

Port the fork's rubric CRUD tools (`create_rubric`, `associate_rubric` enhancements, and `bulk_grade_submissions` improvements) back to the upstream `vishalsachdev/canvas-mcp` repository via a clean Pull Request, adapting to upstream's current code patterns and tool rationalization decisions.

## Problem Frame

The fork added 7 rubric tools that don't exist upstream. However, upstream recently **rationalized rubric tools** (PR #86, merged 2026-04-10) — deliberately deleting `create_rubric`, `update_rubric`, and `delete_rubric` with stated reasons:

| Tool | Upstream's Reason for Removal |
|------|-------------------------------|
| `create_rubric` | "Canvas API 500 bug" |
| `update_rubric` | "Destructive full-replacement API" |
| `delete_rubric` | "Never used, undocumented" |

This means a naive "add all my tools" PR will be rejected. The contribution must:
1. Acknowledge the rationalization that already happened
2. Demonstrate that `create_rubric` works (the "500 bug" may have been specific to their implementation)
3. Respect the upstream maintainer's preference for fewer, well-tested tools
4. Only propose tools that fill genuine gaps

## Requirements Trace

- R1. Open a GitHub Issue proposing the addition before submitting code
- R2. Create a clean feature branch based on `upstream/main` (not the fork's `main`)
- R3. Adapt the code to upstream's current patterns (their imports, decorators, naming)
- R4. Include comprehensive tests that pass against upstream's test infrastructure
- R5. Keep the PR focused — only propose tools with clear value and working Canvas API support
- R6. Document the tools in upstream's format (AGENTS.md tool table, tools/README.md)

## Scope Boundaries

**In scope:**
- `create_rubric` — if the Canvas API 500 issue can be addressed/documented
- `create_account_rubric` — unique capability not found upstream
- `bulk_grade_submissions` improvements (if any exist beyond what upstream moved to assignments.py)

**Explicitly out of scope / Not proposing:**
- `update_rubric` — upstream deliberately removed it; Canvas API's full-replacement behavior is a legitimate concern
- `delete_rubric` — upstream deliberately removed it; low value, safety risk
- `list_assignment_rubrics`, `get_assignment_rubric_details`, `get_rubric_details` — upstream merged these into `get_rubric(rubric_id=None, assignment_id=None)` and won't want them back
- Any fork-specific infrastructure (delete guard, de-anonymization approach)

### Deferred to Separate Tasks

- Contributing the delete guard feature (separate PR, different scope)
- Contributing transdisciplinary discovery tools (separate PR)

## Context & Research

### Upstream's Current State (as of 2026-04-10)

- 5 rubric tools in `rubrics.py` + `bulk_grade_submissions` in `assignments.py`
- Actively maintained (weekly commits, PRs #86-#93 in April)
- 328 tests, uses pytest + pytest-asyncio
- Decorator pattern: `@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))` for reads, `@mcp.tool()` for writes, then `@validate_params`
- Error handling: returns formatted error strings, not JSON
- Has concurrency semaphore, rate limit retry, audit logging in `make_canvas_request`
- Does NOT have `use_form_data` at the `make_canvas_request` level (handled inline)

### Fork's Implementation Details

- `create_rubric` uses form-data encoding with bracket notation (`rubric[title]`, `rubric[criteria][0][description]`)
- `create_account_rubric` uses direct httpx for multipart CSV upload (bypasses `make_canvas_request`)
- Helper functions: `preprocess_criteria_string()`, `validate_rubric_criteria()`, `build_criteria_structure()`, `build_rubric_form_data()`
- 23 tests exist but only cover validation helpers and `create_rubric` success path

### Key Risk: The "Canvas API 500 Bug"

Upstream removed `create_rubric` citing a Canvas API 500 error. Possible explanations:
1. Their implementation had a bug in form-data encoding (likely — this is notoriously tricky with Canvas)
2. Canvas API was temporarily broken (less likely if it persisted)
3. The fork's implementation handles it correctly via proper bracket-notation form data

**Before submitting the PR, this must be verified**: test `create_rubric` against a live Canvas sandbox to confirm it works reliably.

## Key Technical Decisions

- **Open Issue First**: Start with discussion, not code. The maintainer explicitly chose to remove these tools — proposing them back requires justification.
- **Propose `create_rubric` only if verified working**: If the Canvas API 500 is reproducible with the fork's implementation too, don't propose it.
- **Adapt to upstream patterns**: Rewrite the tools to match upstream's coding style, not just copy from fork.
- **Separate branch from upstream/main**: The PR branch must be based on `upstream/main`, not `origin/main`, to avoid carrying fork-specific diffs.
- **Small, focused PR**: 1-2 tools maximum. A 12-tool PR will be rejected.

## Open Questions

### Resolved During Planning

- **Q: Should we propose all 7 new tools?** No. Upstream deliberately removed 3 of them and merged 3 others into `get_rubric`. Only `create_rubric` and `create_account_rubric` are candidates.
- **Q: Should the PR branch live on our fork?** Yes. Push to `origin` (jaymesdec/canvas-mcp), then open PR targeting `vishalsachdev/canvas-mcp:main`.

### Deferred to Implementation

- **Q: Does `create_rubric` actually work against Canvas without 500 errors?** Must be tested live before submitting code.
- **Q: Will upstream accept `create_account_rubric`?** Depends on Issue discussion — this uses CSV upload which is unusual.

## Implementation Units

- [ ] **Unit 1: Verify create_rubric against live Canvas**

**Goal:** Confirm the fork's `create_rubric` implementation works reliably against Canvas LMS, disproving or validating the "Canvas API 500 bug" upstream cited.

**Requirements:** R5

**Dependencies:** None

**Files:**
- Reference: `src/canvas_mcp/tools/rubrics.py` (fork's implementation)
- Create: a test script or manual test log documenting results

**Approach:**
- Run `create_rubric` against a Canvas sandbox course with various criteria structures
- Test edge cases: single criterion, multiple criteria, with/without ratings, with/without association
- Document whether it succeeds, fails with 500, or fails intermittently
- If it fails, investigate whether the form-data encoding differs from what Canvas expects

**Test scenarios:**
- Happy path: Create rubric with 2 criteria, each with 3 ratings -> 200 response, rubric visible in Canvas UI
- Edge case: Create rubric with no ratings (just criteria) -> should succeed or fail gracefully
- Edge case: Create rubric with association to assignment -> rubric appears on assignment
- Error path: Create rubric in non-existent course -> clear error, not 500

**Verification:**
- Clear pass/fail determination documented
- If pass: proceed to Unit 2. If fail: stop and document the issue for the GitHub Issue discussion.

- [ ] **Unit 2: Open GitHub Issue proposing the addition**

**Goal:** Start the upstream conversation before writing any code for them.

**Requirements:** R1

**Dependencies:** Unit 1 (need verified results to reference)

**Files:**
- None (GitHub Issue, not code)

**Approach:**
- Title: something like "feat: Add create_rubric tool for programmatic rubric creation"
- Body should include:
  - The gap: upstream has tools to read/associate/grade with rubrics, but no way to create them programmatically
  - Evidence that it works (from Unit 1 testing)
  - Acknowledgment of PR #86's rationalization and why `create_rubric` specifically adds value
  - Offer to submit a PR if the maintainer is interested
  - Optionally mention `create_account_rubric` as a second candidate
- Tone: collaborative, not presumptuous

**Test expectation:** None — this is a communication task.

**Verification:**
- Issue is open on `vishalsachdev/canvas-mcp`
- Maintainer has been given space to respond before code is written

- [ ] **Unit 3: Create clean feature branch from upstream/main**

**Goal:** Prepare a branch that carries only the rubric creation addition, no fork-specific changes.

**Requirements:** R2

**Dependencies:** Unit 2 (wait for positive signal from maintainer)

**Files:**
- Branch: `feat/create-rubric-tool` based on `upstream/main`

**Approach:**
- `git fetch upstream`
- `git checkout -b feat/create-rubric-tool upstream/main`
- This branch will only be pushed to `origin` (the fork), never upstream directly
- Verify with `git log --oneline -5` that it matches upstream's history exactly

**Test expectation:** None — scaffolding step.

**Verification:**
- Branch exists and is based on upstream/main (no fork-specific commits in history)

- [ ] **Unit 4: Port create_rubric to upstream's patterns**

**Goal:** Rewrite `create_rubric` to match upstream's code style, decorators, error handling, and helper function patterns.

**Requirements:** R3, R5

**Dependencies:** Unit 3

**Files:**
- Modify: `src/canvas_mcp/tools/rubrics.py` (on the new branch)
- Create: test file following upstream's test patterns

**Approach:**
- Add `create_rubric` tool to the existing `register_rubric_tools` function
- Use upstream's decorator stack: `@mcp.tool()` then `@validate_params`
- Use upstream's error handling pattern (formatted strings, not JSON)
- Port the necessary helper functions (`validate_rubric_criteria`, `build_criteria_structure`, `build_rubric_form_data`) as module-level functions
- Handle form-data encoding inline (upstream doesn't have `use_form_data` as a `make_canvas_request` param — check if they do now, otherwise use `httpx` directly or adapt)
- Match upstream's docstring format for the tool

**Patterns to follow:**
- Upstream's `grade_with_rubric` implementation (same file) — for form-data handling
- Upstream's `associate_rubric` — for decorator stack and error patterns
- Upstream's `build_rubric_assessment_form_data()` — for bracket-notation construction

**Test scenarios:**
- Happy path: Create rubric with title and valid criteria list -> success response with rubric ID
- Happy path: Create rubric with assignment association -> rubric created AND associated
- Edge case: Criteria passed as JSON string -> properly parsed and validated
- Edge case: Empty criteria list -> validation error before API call
- Error path: Missing title -> validation error
- Error path: Canvas API returns error -> formatted error message returned
- Error path: Invalid criteria structure (missing description/points) -> clear validation message

**Verification:**
- Tool appears in upstream's test suite and all tests pass
- Code style matches surrounding tools (no fork-specific patterns leak through)
- `pytest` passes with 0 failures

- [ ] **Unit 5: Update upstream documentation**

**Goal:** Add the new tool to upstream's documentation files per their conventions.

**Requirements:** R6

**Dependencies:** Unit 4

**Files:**
- Modify: `AGENTS.md` (tool table entry)
- Modify: `tools/README.md` (full parameter documentation)
- Modify: `tools/TOOL_MANIFEST.json` (machine-readable entry)

**Approach:**
- Follow the existing format in each file exactly
- Keep descriptions concise and consistent with surrounding entries
- Add example prompts to AGENTS.md following their style

**Test expectation:** None — documentation only.

**Verification:**
- Documentation matches upstream's existing format
- No references to fork-specific features

- [ ] **Unit 6: Submit Pull Request**

**Goal:** Open a clean PR from fork to upstream with proper description.

**Requirements:** R2, R3, R4, R5, R6

**Dependencies:** Units 4, 5

**Files:**
- Push branch to `origin` (jaymesdec/canvas-mcp)
- Open PR targeting `vishalsachdev/canvas-mcp:main`

**Approach:**
- Reference the Issue from Unit 2
- PR description should explain:
  - What's added (1 tool: `create_rubric`)
  - Why it's useful (completes the rubric lifecycle: create → associate → grade → assess)
  - How it addresses the Canvas API 500 concern from PR #86
  - Test coverage included
- Keep tone collaborative; be responsive to review feedback

**Test expectation:** None — submission task.

**Verification:**
- PR is open on `vishalsachdev/canvas-mcp`
- CI passes (if they have it)
- PR references the Issue

## System-Wide Impact

- **Interaction graph:** The new tool interacts with `associate_rubric` (users will create then associate) and `grade_with_rubric` (create rubric → associate → grade lifecycle)
- **Error propagation:** Validation errors caught before API call; Canvas API errors returned as formatted strings
- **API surface parity:** Adding a write tool to a currently read-heavy tool set; aligns with upstream's existing `grade_with_rubric` and `associate_rubric` precedent
- **Unchanged invariants:** All 5 existing upstream rubric tools remain unchanged; no modifications to their signatures or behavior

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Maintainer rejects the proposal (they removed it deliberately) | Open Issue first; frame as "the 500 bug may have been implementation-specific"; accept their decision gracefully |
| Canvas API 500 is real and persistent | Unit 1 verifies this before any code work; if confirmed, document it and don't submit |
| Fork's form-data approach doesn't work with upstream's `make_canvas_request` | Study upstream's `grade_with_rubric` (which already does form-data) and follow their pattern exactly |
| PR carries fork-specific commits accidentally | Branch from `upstream/main` explicitly; verify with `git log` before pushing |
| `create_account_rubric` (CSV upload) is too unusual for upstream | Propose it separately in the Issue as optional/future; don't include in first PR |

## Sources & References

- Upstream PR #86: "Rationalize rubric tools: 11 → 6 tools, -540 lines" (merged 2026-04-10)
- Upstream repository: `vishalsachdev/canvas-mcp`
- Fork's implementation: `src/canvas_mcp/tools/rubrics.py`
- Fork's tests: `tests/tools/test_rubrics.py`
