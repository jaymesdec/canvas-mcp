# Student Risk Dashboard

**Date:** 2026-02-05
**Status:** Brainstorm
**Author:** jdec + Claude

## What We're Building

An institution-wide student risk identification system that aggregates data across all courses to identify struggling students before they fail. Serves multiple stakeholders: administrators for intervention, leadership for reporting, and teachers for cross-course visibility.

### Target Users
- **Administrators/Advisors**: Identify at-risk students for early intervention
- **Leadership/Board**: Aggregate success metrics and trends
- **Teachers**: See if their students are struggling in other classes

### Key Capabilities
- Multi-factor risk scoring (grades + missing work + engagement)
- Institution-wide view across all courses in current term
- Natural language queries with export capability
- Real student names for authorized administrators

## Why Query-Based Approach

**Chosen approach**: On-demand risk calculation via MCP tools

### Rationale
1. **Scale fits**: 200-1000 students manageable in real-time queries
2. **Always fresh**: No stale data concerns
3. **Simple infrastructure**: No database or scheduler needed
4. **Conversational fit**: Matches how admins will actually use it
5. **Incremental path**: Can add caching layer later if scale demands

### Rejected Alternatives
- **Cached analytics layer**: Overkill for current scale, adds infrastructure complexity
- **Hybrid caching**: Premature optimization - start simple first

## Key Decisions

### 1. Risk Factors (Multi-Factor Scoring)

| Factor | Weight | Threshold |
|--------|--------|-----------|
| Course grade average | 40% | Below 70% = at risk |
| Missing assignments | 30% | 3+ missing = at risk |
| Late submissions | 15% | Pattern of lateness |
| Engagement decline | 15% | Below peer average activity |

**Risk levels:**
- **High risk**: Score indicates likely to fail without intervention
- **Moderate risk**: Showing warning signs, monitor closely
- **Low risk**: On track

### 2. Scope Constraints

- Filter to current term only (DEFAULT_TERM_ID=155)
- Include only active courses (state=available)
- Exclude test/sandbox courses
- Respect Canvas API rate limits with pagination

### 3. Privacy Model

- Real names shown (ENABLE_DATA_ANONYMIZATION=false for admin use)
- Admin access required for institution-wide queries
- Audit logging for FERPA compliance (use existing pii_audit logger)

### 4. Proposed Tools

| Tool | Purpose | Output |
|------|---------|--------|
| `get_institution_risk_summary` | High-level overview | X students at risk, breakdown by grade/course |
| `list_at_risk_students` | Detailed risk list | Students with risk factors and scores |
| `get_student_risk_profile` | Single student deep-dive | All courses, grades, missing work for one student |
| `export_risk_report` | Export for meetings | CSV with student names, risk factors, courses |

### 5. Example Queries

Administrators would ask:
- "Show me at-risk students across the institution"
- "Which 9th graders are struggling in multiple classes?"
- "Get a risk profile for student John Smith"
- "Export a risk report for the leadership meeting"
- "Which courses have the most at-risk students?"

## Open Questions

1. **Grade level grouping**: Does Franklin School have grade levels (9-12) or other groupings we should support?

2. **Intervention tracking**: Should we track when students were flagged vs. when intervention happened? (May need separate system)

3. **Historical comparison**: Do we want to compare current risk to previous terms? (Adds complexity)

4. **Notification workflow**: Should flagging a student trigger any action, or is this purely reporting?

5. **Teacher permissions**: Can teachers see risk data for students not in their classes? (Privacy consideration)

## Technical Considerations

### API Call Estimation

For 100 courses × 20 students average:
- List courses: 1-2 calls
- Per course enrollments: 100 calls
- Per course assignments: 100 calls
- Per course submissions: 100-500 calls (depends on assignments)

**Total**: ~300-700 API calls for full institution scan

**Mitigation**:
- Use term filtering (already implemented)
- Fetch only active courses
- Limit to recent assignments (last 30 days?)
- Consider chunking large requests

### Data Aggregation Pattern

```
For each student in account:
    For each course they're enrolled in:
        Get their submissions and grades
        Calculate course-level risk factors
    Aggregate across courses
    Compute overall risk score
Return ranked list of at-risk students
```

## Success Criteria

1. Admin can identify top 10 at-risk students in under 30 seconds
2. Risk factors are actionable (specific courses, specific missing work)
3. Export works for board meetings
4. Teachers can see cross-course patterns for their students
5. No false sense of security - system acknowledges limitations

## Next Steps

1. **Plan implementation** - Define exact tool signatures and data flow
2. **Build core tools** - Start with `list_at_risk_students`
3. **Test on sandbox** - Validate with real Franklin School data
4. **Iterate on risk formula** - Tune thresholds based on real patterns
5. **Add export capability** - CSV generation for reports
