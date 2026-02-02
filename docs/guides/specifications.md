# Writing Specifications

Specifications define what ClaudeSprint will build. A well-crafted spec leads to better autonomous execution.

## Spec Location

Place specifications in `.claudesprint/specs/`:

```
.claudesprint/
└── specs/
    ├── SPEC_01.md
    ├── SPEC_02.md
    └── examples/
```

## Spec Structure

```markdown
# SPEC_01 - Feature Name

## Purpose
One paragraph explaining what this feature delivers and why.

## Constraints
- Technical requirements and limitations
- What NOT to do (important for AI guidance)
- Dependencies on other systems

## Deliverables
- Specific, measurable outcomes
- Files or components to be created
- APIs or interfaces to implement

## Work Plan

### 1) First Milestone
- Detailed task description
- Specific acceptance criteria
- Expected behavior

### 2) Second Milestone
- Detailed task description
- Specific acceptance criteria
- Expected behavior

## Acceptance Checklist
- [ ] All tests pass
- [ ] Code review complete
- [ ] Documentation updated
```

## Best Practices

### Be Specific About Constraints

Bad:
```markdown
## Constraints
- Keep it simple
```

Good:
```markdown
## Constraints
- Use only standard library (no external dependencies)
- Must work with Python 3.10+
- Do NOT modify existing API endpoints
- Maximum response time: 100ms
```

### Break Work into Small Issues

Each issue in your Work Plan should be:

- **Completable in one session** - 30-60 minutes of AI work
- **Independently testable** - Has clear pass/fail criteria
- **Focused** - One concern per issue

Bad:
```markdown
### 1) Build the entire authentication system
```

Good:
```markdown
### 1) Create user model and database schema
- Define User model with email, password_hash, created_at
- Add migration script
- Acceptance: `pytest tests/test_user_model.py` passes

### 2) Implement password hashing
- Use bcrypt for password hashing
- Add hash and verify functions
- Acceptance: Unit tests for hash/verify pass

### 3) Add login endpoint
- POST /api/login accepts email/password
- Returns JWT on success, 401 on failure
- Acceptance: Integration tests pass
```

### Include Acceptance Criteria

Every issue should have testable criteria:

```markdown
### 3) Implement URL redirect
- GET /:shortCode redirects to original URL
- Returns 404 for unknown codes
- Logs redirect events

**Acceptance:**
- `curl -I localhost:3000/abc123` returns 302
- `curl -I localhost:3000/notfound` returns 404
- Redirect appears in logs
```

### Specify Technology Choices

Don't leave technology decisions to the AI:

```markdown
## Constraints
- Backend: Express.js with TypeScript
- Database: SQLite with better-sqlite3
- Testing: Vitest
- No ORMs - use raw SQL
```

## Example: URL Shortener Spec

```markdown
# SPEC_01 - URL Shortener Service

## Purpose
Build a URL shortening service that converts long URLs into short,
shareable codes and redirects users to the original destination.

## Constraints
- TypeScript + Express backend
- JSON file for persistence (no database)
- HTMX for frontend interactivity
- Vitest for testing
- No external URL validation APIs

## Deliverables
- REST API for creating/retrieving short URLs
- Web UI for shortening URLs
- Redirect handling for short codes
- Persistent storage across restarts

## Work Plan

### 1) Project Setup
- Initialize Express + TypeScript project
- Configure Vitest
- Add basic health check endpoint
- Acceptance: `npm test` runs, `/health` returns 200

### 2) URL Storage
- Create JSON file storage module
- Implement save/load functions
- Add URL validation
- Acceptance: Unit tests for storage pass

### 3) Shorten Endpoint
- POST /api/shorten accepts { url: string }
- Returns { shortCode: string, shortUrl: string }
- Generates unique 6-character codes
- Acceptance: Can shorten URL via curl

### 4) Redirect Endpoint
- GET /:code redirects to original URL
- Returns 404 for unknown codes
- Acceptance: Redirect works in browser

### 5) Web UI
- Form to submit URLs
- Display shortened result
- HTMX for no-refresh submission
- Acceptance: Manual browser testing

## Acceptance Checklist
- [ ] All Vitest tests pass
- [ ] Can shorten URL via UI
- [ ] Short URLs redirect correctly
- [ ] Data persists after restart
```

## Initializing a Sprint

Convert your spec to a sprint:

```bash
claudesprint init --spec SPEC_01.md
```

This parses the spec and creates `sprint.json` with structured issues.

## Updating a Spec

If you modify a spec mid-sprint:

```bash
claudesprint init --spec SPEC_01.md --update
```

This preserves completed issues and updates remaining ones.
