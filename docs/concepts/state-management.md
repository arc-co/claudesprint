# State Management

ClaudeSprint solves the "context window problem" through explicit state files. Rather than relying on conversational memory (which degrades over long sessions), all context is written to JSON files that are read fresh at each step.

## The Problem with Implicit State

Traditional AI coding assistants maintain state implicitly through conversation history:

```
User: Create a user model
AI: [creates User model]

User: Now add authentication
AI: [has context from previous messages]

User: Fix that bug we discussed
AI: [context window filling up]

... 50 messages later ...

AI: [hallucinating, lost original context]
```

ClaudeSprint inverts this: **nothing is remembered between sessions**. Each step starts fresh, reading only from explicit state files.

## State Files

### `sprint.json`

The sprint file is the source of truth for the entire project sprint. It's created by `claudesprint init` and updated as issues complete.

Location: `.claude/claudesprint/sprints/<SPEC_ID>/sprint.json`

```json
{
  "schema_version": "2.0",
  "spec_id": "SPEC_01",
  "spec_file": ".claude/claudesprint/specs/SPEC_01.md",
  "description": "Counter Application MVP",

  "issues": [
    {
      "id": "setup-001",
      "title": "Project Setup",
      "status": "completed",
      "priority": "critical",
      "category": "setup",
      "acceptance_criteria": [
        "Project initializes with npm install",
        "TypeScript configuration is valid",
        "Development server starts successfully"
      ],
      "dependencies": [],
      "notes": "Foundation for all other issues",
      "history": [
        {
          "timestamp": "2026-01-23T10:00:00Z",
          "action": "started",
          "session_id": "2026-01-23T10:00:00Z/select-issue"
        },
        {
          "timestamp": "2026-01-23T10:30:00Z",
          "action": "completed",
          "session_id": "2026-01-23T10:25:00Z/complete-issue"
        }
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
        {
          "timestamp": "2026-01-23T10:35:00Z",
          "action": "started",
          "session_id": "2026-01-23T10:35:00Z/select-issue"
        }
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
    "total_issues": 4,
    "pending": 2,
    "in_progress": 1,
    "completed": 1,
    "blocked": 0
  }
}
```

#### Key Fields

| Field | Purpose |
|-------|---------|
| `schema_version` | For backward compatibility |
| `spec_id` | Links to source specification |
| `issues[]` | All issues in the sprint |
| `issues[].status` | `pending`, `in_progress`, `completed`, `blocked` |
| `issues[].dependencies` | Other issue IDs that must complete first |
| `issues[].history` | Audit trail of status changes |
| `config` | Workflow behavior flags |
| `metadata` | Aggregated counts (computed) |

#### Modification Rules

- **Agent CAN modify**: `issues[].status`, `issues[].history`, `metadata`, `last_modified`
- **Agent CANNOT modify**: `issues[].title`, `issues[].acceptance_criteria`, `spec_id`, `spec_file`

Changing acceptance criteria requires an explicit planning step, not mid-implementation edits.

### `current_issue.json`

The current issue file contains all context needed for the current step. It's the "baton" passed between sessions.

Location: `.claude/claudesprint/project/current_issue.json`

```json
{
  "schema_version": "2.0",
  "session_id": "2026-01-23T10:45:00Z/implement",
  "timestamp": "2026-01-23T10:45:00Z",

  "sprint_path": ".claude/claudesprint/sprints/SPEC_01/sprint.json",
  "issue_id": "feature-001",
  "issue_title": "Counter Display",

  "step": "implement",
  "goal": "Create Counter component that displays the current count value, initialized to 0",

  "repo_state": {
    "git_head": "abc123def",
    "dirty": false
  },

  "changes": [],
  "commands_run": [],
  "current_failures": "",

  "next_action": "Create src/components/Counter.tsx with a functional component that uses useState to manage count",

  "rationale": [
    "Chose functional component with hooks per project conventions",
    "Using useState for local state as count doesn't need global state"
  ],

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

#### Key Fields

| Field | Purpose |
|-------|---------|
| `session_id` | Unique identifier for this session |
| `sprint_path` | Path to the sprint file |
| `issue_id` | Current issue being worked on |
| `step` | Current workflow step |
| `goal` | Human-readable description of what to accomplish |
| `changes[]` | Files modified so far |
| `commands_run[]` | Commands executed so far |
| `current_failures` | Error message if in failed state |
| `next_action` | Specific next step to execute |
| `rationale[]` | Decisions made and why |
| `retry_count` | Number of retries on current step |
| `context` | Cached data from sprint.json |

#### Lifecycle

1. **Created**: When `select-issue` picks an issue
2. **Updated**: After each step completes
3. **Cleared**: When `complete-issue` finishes

### `current_issue.log`

An append-only log of workflow activity. The last 20 entries are injected into agent context for visibility into recent history.

Location: `.claude/claudesprint/project/current_issue.log`

```
2026-01-23T10:35:00Z [select-issue] Selected issue feature-001: Counter Display
2026-01-23T10:35:01Z [select-issue] Rationale: Dependencies satisfied, high priority
2026-01-23T10:40:00Z [read-docs] Gathered context for React component patterns
2026-01-23T10:40:01Z [read-docs] Found existing Button component to follow as pattern
2026-01-23T10:45:00Z [implement] Starting implementation of Counter component
2026-01-23T10:50:00Z [implement] Created src/components/Counter.tsx
2026-01-23T10:50:01Z [implement] Created src/components/Counter.test.tsx
2026-01-23T10:55:00Z [write-tests] Tests already created during implement step
2026-01-23T11:00:00Z [run-tests] Running npm run validate
2026-01-23T11:00:30Z [run-tests] FAIL: Counter.test.tsx - expected 0, received undefined
2026-01-23T11:00:31Z [run-tests] Routing to fix-tests
2026-01-23T11:05:00Z [fix-tests] Analyzed failure - test expectation was correct
2026-01-23T11:05:01Z [fix-tests] Code bug: useState initial value was missing
2026-01-23T11:05:02Z [fix-tests] Routing back to implement for code fix
```

#### Purpose

- **Debugging**: See what happened in previous steps
- **Continuity**: Agent understands recent workflow without full history
- **Audit Trail**: Track decisions and failures over time

## State Transitions

### Issue Selection

```
Before:
  sprint.json: issue.status = "pending"
  current_issue.json: (empty or previous issue)

After:
  sprint.json: issue.status = "in_progress", history += started
  current_issue.json: populated with issue context, step = "read-docs"
```

### Step Completion

```
Before:
  current_issue.json: step = "implement", changes = []

After:
  current_issue.json: step = "write-tests", changes = [{path, summary}]
  current_issue.log: append implement completion
```

### Test Failure

```
Before:
  current_issue.json: step = "run-tests", retry_count = 0

After (routing to fix-tests):
  current_issue.json: step = "fix-tests", current_failures = "...", retry_count = 1
```

### Issue Completion

```
Before:
  sprint.json: issue.status = "in_progress"
  current_issue.json: populated

After:
  sprint.json: issue.status = "completed", history += completed
  current_issue.json: cleared
  current_issue.log: append completion, ready for next issue
```

## Validation

All state files are validated against JSON schemas before use.

### Schema Locations
- `sprint.json`: `.claude/claudesprint/schemas/sprint.schema.json`
- `current_issue.json`: `.claude/claudesprint/schemas/current_issue.schema.json`

### Validation Command

```bash
claudesprint validate
```

Validates:
- JSON syntax
- Required fields present
- Field types correct
- Step values valid
- Issue ID references exist

### Pre-flight Validation

Before each step executes:
1. Read `current_issue.json`
2. Validate against schema
3. Verify `sprint_path` file exists
4. Verify `issue_id` exists in sprint
5. Verify `step` is valid for current state

If validation fails, the workflow stops with an error.

## Recovery

### Corrupted State

If `current_issue.json` becomes corrupted:

```bash
# Check what's wrong
claudesprint validate

# Reset to clean state
claudesprint reset
```

### Lost Context

If you need to understand what happened:

```bash
# View recent log
tail -50 .claude/claudesprint/project/current_issue.log

# View current issue state
cat .claude/claudesprint/project/current_issue.json | jq .

# View sprint state
cat .claude/claudesprint/sprints/SPEC_01/sprint.json | jq '.issues[] | {id, status}'
```

### Manual State Edits

Sometimes you need to manually fix state:

```bash
# Reset retry count
jq '.retry_count = 0' .claude/claudesprint/project/current_issue.json > tmp && mv tmp .claude/claudesprint/project/current_issue.json

# Force step change
jq '.step = "implement"' .claude/claudesprint/project/current_issue.json > tmp && mv tmp .claude/claudesprint/project/current_issue.json

# Clear failures
jq '.current_failures = ""' .claude/claudesprint/project/current_issue.json > tmp && mv tmp .claude/claudesprint/project/current_issue.json
```

Always run `claudesprint validate` after manual edits.

## Best Practices

### 1. Trust the State Files

Don't rely on terminal history or memory. If it's not in `current_issue.json` or `sprint.json`, it doesn't exist.

### 2. Log Decisions

Use `rationale` in `current_issue.json` to capture why decisions were made. This helps future steps understand context.

### 3. Keep Changes Atomic

Update state after each logical unit of work. Don't batch multiple steps into one state update.

### 4. Validate Often

Run `claudesprint validate` whenever you're unsure about state integrity.

## Next Steps

- [Workflow Steps](./workflow-steps.md): Detailed step documentation
- [Architecture](./architecture.md): How state fits into the dual-loop system
- [Troubleshooting](../reference/troubleshooting.md): Fixing common state issues
