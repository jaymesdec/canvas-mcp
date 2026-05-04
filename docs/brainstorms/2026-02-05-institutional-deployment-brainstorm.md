# Institutional Canvas MCP Deployment

**Date:** 2026-02-05
**Status:** Brainstorm
**Author:** jdec + Claude

## What We're Building

Scale Canvas MCP from individual instructor use to institution-wide deployment supporting multiple user roles with appropriate access controls.

### Target Users
- **Administrators**: Cross-institutional reporting, compliance monitoring
- **Support Staff**: Student troubleshooting, enrollment queries
- **Curriculum Designers**: Course content analysis, teaching pattern insights
- **Researchers**: Interdisciplinary opportunity discovery

### Capabilities
- Read-only analytics across all courses
- Student support queries (individual progress, missing work)
- Course content management (assignments, modules, pages)
- Bulk messaging to students/instructors
- **Unique**: Trans-disciplinary project opportunity discovery

## Why Sandbox-First Rollout

**Chosen approach**: Start with full CRUD in sandbox, graduate to production with phased access.

### Rationale
1. **Risk mitigation**: Primary concern is accidental data changes - sandbox lets us experiment safely
2. **Trust building**: Demonstrate value with read-only production before enabling writes
3. **Learning curve**: Discover edge cases and workflow issues before they affect real courses
4. **Stakeholder buy-in**: Show concrete results in sandbox to justify broader rollout

### Phased Plan
| Phase | Environment | Access Level | Goal |
|-------|-------------|--------------|------|
| 1 | Sandbox | Full CRUD | Test all workflows, identify risks |
| 2 | Production | Read-only | Prove analytics value, build confidence |
| 3 | Production | Tiered tokens | Role-based write access |

## Key Decisions

### 1. Authorization Model: Role-Based Tokens
Create multiple Canvas developer keys with different scopes:
- **Read-only token**: `url:GET` only - for analytics and support queries
- **Educator+ token**: + PUT/POST on content - for curriculum designers
- **Admin token**: Full scope - for emergencies and IT only

### 2. Privacy/FERPA: Enable Anonymization
- Set `ENABLE_DATA_ANONYMIZATION=true` for AI analysis workflows
- Use de-anonymization feature when specific student intervention needed
- Audit logging via `pii_audit` logger for compliance

### 3. Write Operation Safeguards
For Phase 3 (production writes), consider:
- Confirmation prompts for modifications
- "Dry run" mode that shows what would change
- Audit logging of all write operations

## Unique Value Proposition: Interdisciplinary Discovery

The most exciting institutional capability is finding trans-disciplinary collaboration opportunities by analyzing:

1. **Assignment similarities**: Courses with compatible project types
2. **Topic overlap**: Related themes across disciplines
3. **Student crossover**: Students enrolled in complementary courses

Example insight: "BADM 554's sustainable supply chain capstone could partner with ENVS 302's carbon footprint research - 3 students are enrolled in both and could bridge the collaboration."

## Technical Implementation Notes

### Existing Infrastructure (Already Built)
- Enterprise overlay profile in `config/overlays/enterprise.env`
- Anonymization system with FERPA compliance
- De-anonymization with audit logging (`feat/deanonymization` branch)
- Course caching with bidirectional ID resolution
- Security test framework

### Gaps for Institutional Deployment
- [ ] Multi-instance deployment documentation
- [ ] Developer key scope recommendations
- [ ] Cross-course query tools (currently course-scoped)
- [ ] Interdisciplinary analysis tools (new feature)
- [ ] Audit logging implementation (framework exists, features pending)
- [ ] Admin dashboard/reporting (out of scope for MCP?)

## Open Questions

1. **How will users access different token tiers?** Separate MCP server instances? Token switching? User authentication?

2. **What Canvas admin permissions are required** to create developer keys with appropriate scopes?

3. **How do we handle rate limits** when querying across hundreds of courses?

4. **Should interdisciplinary analysis be a new tool** or an enhancement to existing analytics?

5. **What's the governance model** for who can request write access?

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Accidental bulk modification | Medium | High | Read-only default, tiered tokens |
| FERPA violation | Low | Critical | Anonymization enabled, audit logging |
| Rate limit exhaustion | Medium | Medium | Caching, batch queries, backoff |
| Scope creep / misuse | Medium | Medium | Clear documentation, access reviews |
| API token exposure | Low | High | Environment variables, no logging of tokens |

## Next Steps

1. **Immediate**: Set up Canvas sandbox with developer key
2. **Week 1**: Test full CRUD workflows in sandbox
3. **Week 2**: Document findings, identify production-ready features
4. **Week 3**: Deploy read-only to production for analytics pilot
5. **Ongoing**: Evaluate, gather feedback, expand capabilities

---

## Appendix: Developer Key Scope Reference

Canvas developer keys support these scope patterns:
- `url:GET|/api/v1/courses/:course_id/assignments` - Read assignments
- `url:POST|/api/v1/courses/:course_id/assignments` - Create assignments
- `url:PUT|/api/v1/courses/:course_id/assignments/:id` - Update assignments

For read-only analytics, restrict to `url:GET|*` patterns only.

See: Canvas API documentation for full scope syntax.
