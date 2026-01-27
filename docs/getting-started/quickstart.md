# Quickstart

This guide walks you through running ClaudeSprint from zero to a completed sprint. You'll see the orchestrator in action—autonomously selecting issues, implementing features, running tests, and committing code.

## Prerequisites

Ensure you have completed [Installation](./installation.md) and can run:

```bash
source .venv/bin/activate
claudesprint status
```

## Step 1: Initialize from the Demo Spec

ClaudeSprint includes a "Textbook Exchange" demo specification that showcases the full power of the orchestrator—database setup, authentication, and UI components working together.

View the included spec to understand what will be built:

```bash
cat .claude/claudesprint/specs/examples/textbook-exchange.md
```

This spec defines a minimal textbook exchange app with:
- Express + TypeScript + SQLite stack
- User authentication (register/login/logout)
- Listing creation and browsing
- Server-rendered views with Handlebars

Copy it to your specs directory and initialize:

```bash
cp .claude/claudesprint/specs/examples/textbook-exchange.md .claude/claudesprint/specs/SPEC_01.md
claudesprint init --spec SPEC_01.md
```

This creates:
- A git branch: `sprint/SPEC_01`
- A sprint file: `.claude/claudesprint/sprints/SPEC_01/sprint.json`
- Issues with acceptance criteria derived from the spec

Inspect the generated sprint:

```bash
cat .claude/claudesprint/sprints/SPEC_01/sprint.json | jq '.issues[] | {id, title, priority, status}'
```

You'll see issues like:
```json
{"id": "setup-001", "title": "Project Setup", "priority": "critical", "status": "pending"}
{"id": "db-001", "title": "Database Schema", "priority": "critical", "status": "pending"}
{"id": "auth-001", "title": "User Authentication", "priority": "high", "status": "pending"}
{"id": "feature-001", "title": "Listings Feature", "priority": "high", "status": "pending"}
{"id": "ui-001", "title": "Styling and Polish", "priority": "medium", "status": "pending"}
```

## Step 2: Run the Sprint

Start the autonomous workflow:

```bash
claudesprint run
```

The orchestrator will:
1. **Select an issue** based on priority and dependencies
2. **Read documentation** for relevant context
3. **Implement** the feature with minimal code changes
4. **Write tests** for acceptance criteria
5. **Run tests** and fix any failures
6. **Browser validation** (if UI-related)
7. **Code review** against the specification
8. **Commit changes** after all gates pass
9. **Mark complete** and select the next issue

### Watching Progress

In a separate terminal, you can watch the workflow:

```bash
# Watch the log
tail -f .claude/claudesprint/project/current_issue.log

# Check current status
watch -n 5 claudesprint status
```

### Limiting Iterations

To run a specific number of iterations (useful for testing):

```bash
# Run up to 10 iterations then stop
claudesprint run -n 10
```

## Step 3: Monitor and Intervene

### Check Status

```bash
claudesprint status
```

Example output:
```
ClaudeSprint Status
==================
Current Issue: auth-001 (User Authentication)
Step: run-tests
Retry Count: 0

Sprint: SPEC_01
  Completed: 2/5
  In Progress: 1
  Pending: 2
```

### View Recent Activity

```bash
tail -20 .claude/claudesprint/project/current_issue.log
```

### Pause the Workflow

The workflow respects Ctrl+C. It will finish the current step and exit cleanly. Resume with:

```bash
claudesprint run
```

### Reset and Start Fresh

If something goes wrong:

```bash
# Reset current issue state
claudesprint reset

# The sprint file is preserved; only the current issue context is cleared
claudesprint status
```

## Step 4: Review Completed Work

After issues complete, review what was built:

```bash
# See recent commits
git log --oneline -10

# See all changes since sprint started
git diff main..sprint/SPEC_01

# Run the application
npm run dev
```

## Understanding the Output

### Sprint File Updates

As issues complete, `sprint.json` is updated:

```json
{
  "id": "feature-001",
  "status": "completed",
  "history": [
    {"timestamp": "...", "action": "started", "session_id": "..."},
    {"timestamp": "...", "action": "completed", "session_id": "..."}
  ]
}
```

### Commit Messages

Each completed issue creates a commit:

```
feat(auth): implement user authentication

- Add register/login/logout routes
- Hash passwords with bcrypt
- Session management with express-session
- Add auth middleware for protected routes

Acceptance Criteria:
- [x] User can register with username/password
- [x] User can login and logout
- [x] Passwords are hashed (not stored in plain text)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Common Scenarios

### Test Failures

If tests fail, the workflow automatically:
1. Analyzes whether it's a code bug or test bug
2. Routes to `fix-tests` or back to `implement`
3. Retries up to the max retry limit

### Code Review Issues

If code review finds problems, the workflow:
1. Routes to `fix-code-review-issues`
2. Makes targeted fixes
3. Re-runs tests
4. Returns to code review

### Max Retry Exceeded

If the workflow hits the retry limit:

```bash
# Check what failed
cat .claude/claudesprint/project/current_issue.json | jq '.current_failures'

# Fix the issue manually, then reset retry count
jq '.retry_count = 0' .claude/claudesprint/project/current_issue.json > tmp && mv tmp .claude/claudesprint/project/current_issue.json

# Continue
claudesprint run
```

## What's Next?

You've now seen ClaudeSprint autonomously build a full-stack application with authentication, database, and UI. For your own projects:

1. **[Specifications and Scoping](../guides/specifications-and-scoping.md)**: Write effective specs that guide the agent
2. **[Configuration](../guides/configuration.md)**: Customize hooks, models, and settings
3. **[Architecture](../concepts/architecture.md)**: Understand the dual-loop system in depth
4. **[Advanced Workflows](../guides/advanced-workflows.md)**: Run parallel sprints, handle complex projects

## Quick Reference

```bash
# Initialize a sprint from a spec
claudesprint init --spec SPEC_01.md

# Run the workflow
claudesprint run

# Limit iterations
claudesprint run -n 10

# Check status
claudesprint status

# View sprints
claudesprint sprints

# Reset current issue
claudesprint reset

# Validate state files
claudesprint validate

# View model configuration
claudesprint models
```
