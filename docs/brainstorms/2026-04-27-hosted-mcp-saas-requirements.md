---
date: 2026-04-27
topic: hosted-mcp-saas
---

# Hosted Canvas MCP Server (SaaS)

## Problem Frame

Canvas MCP provides 83+ tools for teachers to interact with Canvas LMS through AI assistants. The current setup requires teachers to install Python, `uv`, configure environment variables, generate Canvas API tokens, and wire up MCP client config — a process that's too technical for most educators. Multiple teachers at other schools have expressed interest but can't get past the installation barrier.

A hosted version would let teachers sign up, connect their Canvas account, and get a remote MCP server endpoint they can plug into any MCP-compatible AI client (Claude Desktop, Cursor, etc.) — no local installation required.

## Requirements

**Teacher Onboarding**

- R1. Teachers sign up via a web portal with email/password authentication
- R2. Teachers connect their Canvas account by pasting their Canvas API token and Canvas instance URL into the portal
- R3. Teachers receive a unique remote MCP server endpoint URL after connecting their Canvas account
- R4. The portal provides copy-paste instructions for configuring Claude Desktop, Cursor, and other popular MCP clients with the teacher's endpoint

**Remote MCP Server**

- R5. The server exposes a curated starter set of ~15-20 Canvas MCP tools via MCP HTTP transport (Streamable HTTP or HTTP+SSE, whichever has broadest client support at implementation time)
- R6. Each teacher's MCP endpoint authenticates requests (e.g., via bearer token or API key) so only the teacher can invoke their tools
- R7. Canvas API calls are made server-side using the teacher's stored Canvas token, with results returned to the MCP client
- R8. The curated tool set covers the most common teacher workflows: course listing, assignment management, grade viewing, discussion browsing, student analytics, and messaging

**Zero-Persistence Data Architecture**

Student data is never persisted; teacher account and billing data are persisted as described in R12.

- R9. Student data (names, grades, submissions, discussion posts) is processed in-memory only and never written to a database, log file, or persistent storage
- R10. Canvas API responses are passed through to the MCP client and discarded from server memory after the response completes
- R11. Server logs capture request metadata (teacher ID, tool name, timestamp, response status) but never log Canvas API response bodies or student PII
- R12. The only persistent data stored is: teacher account info, encrypted Canvas API tokens, Canvas instance URLs, and billing/subscription state

**Subscription & Billing**

- R13. Access is gated by a flat monthly subscription fee
- R14. Teachers can sign up, manage their subscription, and cancel through the web portal
- R15. Unpaid or expired accounts have their MCP endpoint disabled (returns auth error) but account data is retained for 30 days for reactivation

**Security**

- R16. Canvas API tokens are encrypted at rest using a server-side encryption key (not stored in plaintext)
- R17. All traffic between MCP clients and the hosted server uses TLS
- R18. Per-teacher rate limiting prevents abuse and protects against runaway MCP clients

## Success Criteria

- A teacher with no technical background can go from "heard about this" to "working MCP tools in Claude Desktop" in under 10 minutes
- The hosted server handles concurrent teachers without cross-tenant data leakage
- Monthly subscription revenue covers hosting costs with margin by ~50 paying users

## Scope Boundaries

- **Not in MVP**: Canvas OAuth flow (teachers paste API tokens manually for now)
- **Not in MVP**: All 83+ tools — start with a curated 15-20 tool starter set
- **Not in MVP**: Per-school or district licensing — individual teacher subscriptions only
- **Not in MVP**: Usage-based pricing or tiered plans
- **Not in MVP**: Admin dashboard for schools to manage multiple teacher accounts
- **Not in scope**: Modifying the existing local/open-source Canvas MCP server — the hosted version is a separate product that reuses the tool implementations
- **Not in scope**: Mobile app or custom AI chat interface — teachers bring their own MCP client

## Key Decisions

- **API token paste over Canvas OAuth**: Faster to build, no Instructure developer key approval needed. OAuth is a V2 upgrade once there are paying users.
- **Zero-persistence over full data storage**: Minimizes FERPA compliance surface. The server is a pass-through proxy, not a student data warehouse. This simplifies DPA conversations with school districts.
- **Flat monthly fee over usage-based pricing**: Simplest billing model, predictable revenue, no metering infrastructure needed for MVP.
- **Curated tool set over full suite**: Reduces testing surface for MVP, lets you validate demand before porting all 83+ tools. Expansion is low-effort since tools are already built.
- **Separate product, shared tool code**: The hosted version imports tool implementations from the existing codebase but wraps them in a multi-tenant HTTP server. The open-source local version continues to exist.

## Alternatives Considered

| Approach | Verdict | Rationale |
|----------|---------|-----------|
| One-click local installer (Electron/.app) | Deferred | Eliminates FERPA concerns but still requires local installation and is harder to monetize via subscription |
| Hybrid portal + local execution | Rejected for MVP | More complex architecture (two things to maintain) for marginal FERPA benefit over zero-persistence |
| Full data persistence (student analytics DB) | Rejected | Creates significant FERPA liability and DPA burden without clear user value for MVP |

## Dependencies / Assumptions

- MCP clients (Claude Desktop, Cursor) support remote MCP servers via HTTP transport — this is actively shipping in 2025-2026 but client support varies. Must verify which transport protocol has broadest compatibility at implementation time.
- Canvas API tokens generated by teachers have sufficient permissions for the curated tool set (read access to courses, assignments, grades, discussions, students)
- Instructure's API terms of service permit a third-party hosted service to make Canvas API calls on behalf of authenticated users — **this must be verified before launch**
- A payment processor (Stripe or similar) handles subscription billing; the portal integrates with their API

## Outstanding Questions

### Resolve Before Planning

- [Affects all][Legal/business] Do Instructure's Canvas API terms of service permit a commercial third-party service to proxy API calls on behalf of teachers? Review the [Canvas API Policy](https://www.instructure.com/policies/api-policy) and developer terms.
- [Affects R13][Business] What price point? Need to research comparable EdTech SaaS tools for teachers to establish a reasonable monthly fee ($5-20/month range likely, but needs market validation).

### Deferred to Planning

- [Affects R5][Needs research] Which MCP HTTP transport protocol (Streamable HTTP vs. HTTP+SSE) has the broadest client support across Claude Desktop, Cursor, Windsurf, and other MCP clients as of mid-2026?
- [Affects R5][Technical] Which 15-20 tools should be in the curated starter set? Requires analyzing which tools are most commonly used in the current local deployment.
- [Affects R7][Technical] Multi-tenant architecture: how to inject per-teacher Canvas credentials into the existing tool implementations without rewriting them (e.g., `contextvars`, request-scoped config, or per-request client instances)?
- [Affects R12][Technical] Encryption approach for stored Canvas tokens — application-level encryption (e.g., Fernet/AES) vs. cloud KMS (AWS KMS, GCP KMS)?
- [Affects R1, R14][Technical] Auth and billing integration — which identity provider and payment processor to use?
- [Affects R9-R11][Needs research] What does a "zero-persistence" DPA look like for school districts? Are there templates from other EdTech pass-through services?
- [Affects deployment][Technical] Cloud platform and infrastructure choices (container orchestration, database for teacher accounts, secrets management)

## Deferred / Open Questions

### From 2026-04-27 review

- **Global singleton architecture invalidates "shared tool code" premise** — Key Decisions (P0, feasibility + product + adversarial, confidence 1.00)

  The codebase uses 6+ process-global singletons (Config, httpx client, course caches, anonymization cache). Every tool calls `make_canvas_request()` which uses a single hardcoded Canvas token. Multi-tenant credential injection isn't a planning question — it determines whether the shared-code premise holds at all. A spike to quantify the refactoring is a prerequisite before planning.

  <!-- dedup-key: section="key decisions" title="global singleton architecture invalidates shared tool code premise" evidence="Key Decisions: Separate product, shared tool code: The hosted version imports tool" -->

- **Instructure API ToS is a viability question, not a launch checklist item** — Dependencies / Assumptions (P0, coherence + product + adversarial, confidence 0.98)

  Every requirement depends on this single assumption. If Instructure prohibits commercial proxying, there is zero product — not a reduced product, zero product. This should be the sole gate before any further investment, not one of two equal-weight blockers alongside pricing.

  <!-- dedup-key: section="dependencies  assumptions" title="instructure api tos is a viability question not a launch checklist item" evidence="Instructures API terms of service permit a thirdparty hosted service to make" -->

- **Token-paste onboarding contradicts 10-minute success criterion** — Success Criteria (P0, product + adversarial, confidence 0.95)

  The problem frame says installation is "too technical for most educators," but the solution still requires navigating Canvas Settings to generate an API token — a step outside the product's control. Some institutions restrict token generation entirely. The 10-minute criterion may be unachievable without OAuth.

  <!-- dedup-key: section="success criteria" title="tokenpaste onboarding contradicts 10minute success criterion" evidence="Teachers connect their Canvas account by pasting their Canvas API token and Canvas" -->

- **Encryption key management unspecified** — Security (P0, security, confidence 0.88)

  R16 requires encryption at rest but doesn't address how the encryption key is protected. If the key lives in the same environment as the encrypted tokens, a server breach yields all Canvas tokens in plaintext — single point of failure for multi-tenant student PII access.

  <!-- dedup-key: section="security" title="encryption key management unspecified" evidence="R16 Canvas API tokens are encrypted at rest using a serverside encryption key not" -->

- **MCP endpoint auth mechanism unspecified** — Remote MCP Server (P0, scope-guardian, confidence 0.88)

  R6 says endpoints authenticate but doesn't specify the mechanism (API key, JWT, mTLS). R3 (endpoint URL format), R7 (token routing), R18 (rate limiting) all depend on this choice. Planning cannot scope the auth infrastructure without it.

  <!-- dedup-key: section="remote mcp server" title="mcp endpoint auth mechanism unspecified" evidence="R6 Each teachers MCP endpoint authenticates requests eg via bearer token or API" -->

- **Zero-persistence framing ignores MCP client data retention** — Zero-Persistence Data Architecture (P1, product + adversarial, confidence 1.00)

  The server doesn't persist student data, but it passes it to MCP clients (Claude Desktop, Cursor) which persist it in conversation logs and send it to AI providers. School district DPA reviewers will ask "where does student data end up?" — zero-persistence solves server-side liability but doesn't address the full data flow.

  <!-- dedup-key: section="zeropersistence data architecture" title="zeropersistence framing ignores mcp client data retention" evidence="Canvas API responses are passed through to the MCP client and discarded from" -->

- **No handling for Canvas token expiration or revocation** — Requirements (P1, feasibility + product + security + adversarial, confidence 0.98)

  When a token expires or gets revoked by a Canvas admin, every tool call fails silently. No requirement for token health checks, teacher notification, or self-service re-authentication. For non-technical paying users, this creates a support nightmare with no visible recovery path.

  <!-- dedup-key: section="requirements" title="no handling for canvas token expiration or revocation" evidence="Teachers connect their Canvas account by pasting their Canvas API token and Canvas" -->

- **Cross-tenant cache contamination in course code caches** — Requirements R7, R9 (P1, feasibility, confidence 0.92)

  Course code-to-ID caches are global dicts. If two teachers from different schools both have "ENG_101", the cache returns whichever was looked up last. This is a data integrity bug and potential FERPA violation in multi-tenant mode.

  <!-- dedup-key: section="requirements r7 r9" title="crosstenant cache contamination in course code caches" evidence="core/cache.py lines 910: course_code_to_id_cache: dict[str str] = {} and" -->

- **Teacher portal auth underspecified** — Teacher Onboarding (P1, security, confidence 0.85)

  R1 says email/password but no requirements for password policy, MFA, account recovery, or session management. Weak portal auth gives direct access to stored Canvas API tokens for all a teacher's students.

  <!-- dedup-key: section="teacher onboarding" title="teacher portal auth underspecified" evidence="R1 Teachers sign up via a web portal with emailpassword authentication" -->

- **Canvas API token ownership not validated** — Teacher Onboarding (P1, security, confidence 0.82)

  R2 accepts any pasted token without verifying it belongs to the teacher who signed up. An attacker could paste a stolen token to gain access to another teacher's courses and student data.

  <!-- dedup-key: section="teacher onboarding" title="canvas api token ownership not validated" evidence="R2 Teachers connect their Canvas account by pasting their Canvas API token and" -->

- **Fork ownership unexamined for commercial product** — Key Decisions (P1, feasibility + product, confidence 0.82)

  The codebase is a fork of vishalsachdev/canvas-mcp (MIT license). While MIT permits commercial use, the document doesn't acknowledge the fork relationship or address business risks (upstream competition, divergence management, relationship with original author).

  <!-- dedup-key: section="key decisions" title="fork ownership unexamined for commercial product" evidence="Key Decisions: Separate product, shared tool code: The hosted version imports tool" -->

- **MCP HTTP transport readiness uncertain** — Requirements R5 (P1, feasibility + product, confidence 0.80)

  The product depends on MCP clients supporting remote HTTP servers. The current codebase runs stdio-only. Whether FastMCP 2.14+ supports HTTP transport and whether Claude Desktop/Cursor can connect to remote servers should be verified before planning, not during planning.

  <!-- dedup-key: section="requirements r5" title="mcp http transport readiness uncertain" evidence="R5 The server exposes a curated starter set of 1520 Canvas MCP tools via MCP" -->

- **Rate limiting underspecified for multi-tenant Canvas API usage** — Security (P2, security + scope + adversarial, confidence 0.88)

  R18 says "per-teacher rate limiting" but Canvas rate limits are per-institution (~700 req/10min). Multiple teachers from the same school share that budget. Per-teacher server-side limits don't prevent aggregate institution-level rate limit exhaustion.

  <!-- dedup-key: section="security" title="rate limiting underspecified for multitenant canvas api usage" evidence="R18 Perteacher rate limiting prevents abuse and protects against runaway MCP clients" -->

- **50-user breakeven criterion is unfalsifiable** — Success Criteria (P2, product + adversarial, confidence 0.90)

  No cost model, no price point, no demand validation. Interest from people who couldn't install free software is not the same as willingness to pay monthly. A waitlist or letters of intent from even 5 teachers would de-risk significantly.

  <!-- dedup-key: section="success criteria" title="50user breakeven criterion is unfalsifiable" evidence="Monthly subscription revenue covers hosting costs with margin by 50 paying users" -->

- **R5 vs R8 tool set scope ambiguity** — Requirements / Remote MCP Server (P2, coherence, confidence 0.76)

  R5 says "~15-20 tools" (count-bounded), R8 lists functional areas. A reader can't tell whether the tool set is bounded by count or by function. Clarify which is authoritative.

  <!-- dedup-key: section="requirements  remote mcp server" title="r5 vs r8 tool set scope ambiguity" evidence="R5 The server exposes a curated starter set of 1520 Canvas MCP tools via MCP" -->

- **R3 "receive" wording ambiguous** — Teacher Onboarding (P2, coherence, confidence 0.82)

  "Teachers receive a unique remote MCP server endpoint URL" could mean "are shown" (displayed in browser) or "are issued" (generated and sent). Clarify.

  <!-- dedup-key: section="teacher onboarding" title="r3 receive wording ambiguous" evidence="R3 Teachers receive a unique remote MCP server endpoint URL after connecting their" -->

- **R15 data retention underspecified** — Subscription & Billing (P2, coherence + scope, confidence 0.79)

  30-day window start point undefined (cancellation? expiration? first non-payment?). Retention scope unclear relative to zero-persistence claims — does "account data" include encrypted Canvas tokens?

  <!-- dedup-key: section="subscription  billing" title="r15 data retention underspecified" evidence="R15 Unpaid or expired accounts have their MCP endpoint disabled returns auth error" -->

## Next Steps

-> Resolve the two blocking questions (Canvas API terms of service, price point research), then address the review findings above before proceeding to `/ce-plan`
