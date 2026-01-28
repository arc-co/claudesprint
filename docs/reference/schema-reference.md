# Schema Reference

This document provides detailed specifications for ClaudeSprint's JSON schemas.

## sprint.json

The sprint file defines all issues for a specification and tracks their status.

### Location

`.claudesprint/sprints/<SPEC_ID>/sprint.json`

### Full Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": [
    "schema_version",
    "spec_id",
    "spec_file",
    "description",
    "issues",
    "config",
    "created_at",
    "last_modified"
  ],
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "2.0"
    },
    "spec_id": {
      "type": "string",
      "pattern": "^[A-Z0-9_]+$"
    },
    "spec_file": {
      "type": "string"
    },
    "description": {
      "type": "string"
    },
    "issues": {
      "type": "array",
      "items": { "$ref": "#/$defs/issue" }
    },
    "config": {
      "$ref": "#/$defs/config"
    },
    "git_branch": {
      "type": "string"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "last_modified": {
      "type": "string",
      "format": "date-time"
    },
    "metadata": {
      "$ref": "#/$defs/metadata"
    }
  }
}
```

### Field Definitions

#### Root Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | Yes | Schema version, must be "2.0" |
| `spec_id` | string | Yes | Unique identifier (e.g., "SPEC_01") |
| `spec_file` | string | Yes | Path to source specification |
| `description` | string | Yes | Brief sprint description |
| `issues` | array | Yes | List of issue objects |
| `config` | object | Yes | Workflow configuration |
| `git_branch` | string | No | Git branch for this sprint |
| `created_at` | datetime | Yes | Creation timestamp |
| `last_modified` | datetime | Yes | Last modification timestamp |
| `metadata` | object | No | Aggregated statistics |

#### Issue Object

```json
{
  "id": "feature-001",
  "title": "Counter Display",
  "status": "pending",
  "priority": "high",
  "category": "feature",
  "acceptance_criteria": [
    "Counter displays current count",
    "Initial count is 0"
  ],
  "dependencies": ["setup-001"],
  "notes": "Optional implementation notes",
  "history": []
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique issue identifier |
| `title` | string | Yes | Short descriptive title |
| `status` | enum | Yes | `pending`, `in_progress`, `completed`, `blocked` |
| `priority` | enum | Yes | `critical`, `high`, `medium`, `low` |
| `category` | enum | Yes | `setup`, `infrastructure`, `feature`, `api`, `ui`, `testing`, `docs`, `bugfix` |
| `acceptance_criteria` | array | Yes | List of testable criteria |
| `dependencies` | array | No | IDs of blocking issues |
| `notes` | string | No | Additional context |
| `history` | array | No | Status change history |

#### Status Values

| Status | Description |
|--------|-------------|
| `pending` | Not yet started |
| `in_progress` | Currently being worked on |
| `completed` | Successfully finished |
| `blocked` | Cannot proceed (manual intervention needed) |

#### Priority Values

| Priority | Description | Selection Order |
|----------|-------------|-----------------|
| `critical` | Must be done first | 1 |
| `high` | Important for sprint success | 2 |
| `medium` | Normal priority | 3 |
| `low` | Nice to have | 4 |

#### Category Values

| Category | Description | Browser Validation |
|----------|-------------|-------------------|
| `setup` | Project initialization | No |
| `infrastructure` | Build, deploy, CI/CD | No |
| `feature` | Core functionality | Yes (if UI) |
| `api` | Backend endpoints | No |
| `ui` | User interface | Yes |
| `testing` | Test infrastructure | No |
| `docs` | Documentation | No |
| `bugfix` | Bug fixes | Depends |

#### History Entry

```json
{
  "timestamp": "2026-01-23T10:30:00Z",
  "action": "started",
  "session_id": "2026-01-23T10:30:00Z/select-issue"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | datetime | When action occurred |
| `action` | string | `started`, `completed`, `blocked`, `unblocked` |
| `session_id` | string | Session that made the change |

#### Config Object

```json
{
  "require_testing": true,
  "require_browser_qa": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `require_testing` | boolean | true | Must run tests |
| `require_browser_qa` | boolean | false | Must run browser validation |

#### Metadata Object

```json
{
  "total_issues": 4,
  "pending": 2,
  "in_progress": 1,
  "completed": 1,
  "blocked": 0
}
```

Computed from issues array. Updated when issues change status.

### Example Complete Sprint

```json
{
  "schema_version": "2.0",
  "spec_id": "SPEC_01",
  "spec_file": ".claudesprint/specs/SPEC_01.md",
  "description": "Counter Application MVP",
  "issues": [
    {
      "id": "setup-001",
      "title": "Project Setup",
      "status": "completed",
      "priority": "critical",
      "category": "setup",
      "acceptance_criteria": [
        "npm install succeeds",
        "npm run dev starts server",
        "TypeScript compiles without errors"
      ],
      "dependencies": [],
      "notes": null,
      "history": [
        {"timestamp": "2026-01-23T10:00:00Z", "action": "started", "session_id": "..."},
        {"timestamp": "2026-01-23T10:30:00Z", "action": "completed", "session_id": "..."}
      ]
    },
    {
      "id": "feature-001",
      "title": "Counter Display",
      "status": "in_progress",
      "priority": "high",
      "category": "feature",
      "acceptance_criteria": [
        "Counter component displays current count",
        "Initial count value is 0"
      ],
      "dependencies": ["setup-001"],
      "notes": null,
      "history": [
        {"timestamp": "2026-01-23T10:35:00Z", "action": "started", "session_id": "..."}
      ]
    }
  ],
  "config": {
    "require_testing": true,
    "require_browser_qa": false
  },
  "git_branch": "sprint/SPEC_01",
  "created_at": "2026-01-23T09:00:00Z",
  "last_modified": "2026-01-23T10:35:00Z",
  "metadata": {
    "total_issues": 2,
    "pending": 0,
    "in_progress": 1,
    "completed": 1,
    "blocked": 0
  }
}
```

---

## current_issue.json

The current issue file contains all context for the active workflow step.

### Location

`.claudesprint/project/current_issue.json`

### Full Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": [
    "schema_version",
    "session_id",
    "timestamp",
    "sprint_path",
    "issue_id",
    "issue_title",
    "step",
    "goal",
    "context"
  ],
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "2.0"
    },
    "session_id": {
      "type": "string"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "sprint_path": {
      "type": "string"
    },
    "issue_id": {
      "type": "string"
    },
    "issue_title": {
      "type": "string"
    },
    "step": {
      "type": "string",
      "enum": [
        "select-issue",
        "read-docs",
        "implement",
        "write-tests",
        "run-tests",
        "fix-tests",
        "browser-validation",
        "code-review",
        "fix-code-review-issues",
        "update-docs",
        "stage-changes",
        "commit-changes",
        "complete-issue"
      ]
    },
    "goal": {
      "type": "string"
    },
    "repo_state": {
      "$ref": "#/$defs/repoState"
    },
    "changes": {
      "type": "array",
      "items": { "$ref": "#/$defs/change" }
    },
    "commands_run": {
      "type": "array",
      "items": { "type": "string" }
    },
    "current_failures": {
      "type": "string"
    },
    "next_action": {
      "type": "string"
    },
    "retry_count": {
      "type": "integer",
      "minimum": 0
    },
    "context": {
      "$ref": "#/$defs/issueContext"
    }
  }
}
```

### Field Definitions

#### Root Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | Yes | Must be "2.0" |
| `session_id` | string | Yes | Unique session identifier |
| `timestamp` | datetime | Yes | Current timestamp |
| `sprint_path` | string | Yes | Path to sprint.json |
| `issue_id` | string | Yes | ID of current issue |
| `issue_title` | string | Yes | Title of current issue |
| `step` | enum | Yes | Current workflow step |
| `goal` | string | Yes | Human-readable goal |
| `repo_state` | object | No | Git repository state |
| `changes` | array | No | Files modified |
| `commands_run` | array | No | Commands executed |
| `current_failures` | string | No | Error message if failed |
| `next_action` | string | No | Next action to take |
| `retry_count` | integer | No | Retry attempts on current step |
| `context` | object | Yes | Issue context from sprint |

#### Step Values

| Step | Description |
|------|-------------|
| `select-issue` | Choosing next issue |
| `read-docs` | Gathering documentation |
| `implement` | Writing code |
| `write-tests` | Creating tests |
| `run-tests` | Executing test suite |
| `fix-tests` | Fixing test failures |
| `browser-validation` | E2E browser testing |
| `code-review` | Reviewing implementation |
| `fix-code-review-issues` | Addressing review findings |
| `update-docs` | Updating documentation |
| `stage-changes` | Git staging |
| `commit-changes` | Creating commit |
| `complete-issue` | Finalizing issue |

#### Repo State Object

```json
{
  "git_head": "abc123def",
  "dirty": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `git_head` | string | Current commit SHA |
| `dirty` | boolean | Has uncommitted changes |

#### Change Object

```json
{
  "path": "src/components/Counter.tsx",
  "summary": "Created Counter component with useState"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | File path relative to root |
| `summary` | string | Brief description of change |

#### Issue Context Object

```json
{
  "acceptance_criteria": [
    "Counter displays current count",
    "Initial count is 0"
  ],
  "category": "feature"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `acceptance_criteria` | array | Copied from sprint issue |
| `category` | string | Issue category |

### Example Complete Current Issue

```json
{
  "schema_version": "2.0",
  "session_id": "2026-01-23T10:45:00Z/implement",
  "timestamp": "2026-01-23T10:45:00Z",
  "sprint_path": ".claudesprint/sprints/SPEC_01/sprint.json",
  "issue_id": "feature-001",
  "issue_title": "Counter Display",
  "step": "implement",
  "goal": "Create Counter component that displays current count, initialized to 0",
  "repo_state": {
    "git_head": "abc123def",
    "dirty": false
  },
  "changes": [],
  "commands_run": [],
  "current_failures": "",
  "next_action": "Create src/components/Counter.tsx with functional component using useState",
  "retry_count": 0,
  "context": {
    "acceptance_criteria": [
      "Counter component displays current count",
      "Initial count value is 0"
    ],
    "category": "feature"
  }
}
```

---

## Schema Files

The JSON Schema files are bundled with the Python package at:

- `claudesprint/schemas/sprint.schema.json`
- `claudesprint/schemas/current_issue.schema.json`

These are accessed programmatically via `PathService.get_schema_content()` and are not user-editable.

### Validating Against Schemas

```bash
# Using claudesprint CLI
claudesprint validate

# Using jq (manual validation)
jq empty .claudesprint/sprints/SPEC_01/sprint.json
jq empty .claudesprint/project/current_issue.json
```

### Common Validation Errors

| Error | Cause | Fix |
|-------|-------|-----|
| Missing required field | Field not present | Add the field |
| Invalid enum value | Value not in allowed list | Use valid value |
| Type mismatch | Wrong data type | Convert to correct type |
| Invalid datetime | Bad format | Use ISO 8601 format |

## Next Steps

- [CLI Commands](./cli-commands.md): Command reference
- [Troubleshooting](./troubleshooting.md): Fix common issues
- [State Management](../concepts/state-management.md): How state flows
