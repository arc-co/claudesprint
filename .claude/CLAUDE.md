# CLAUDE.md - Project Intelligence

## Project Overview

This project uses ClaudeSprint for AI-driven development. All agentic infrastructure lives in `.claude/`. Project code stays clean in root.

## Quick Start

```bash
./setup.sh && source .venv/bin/activate && claudesprint status
```

## Build & Test Commands

```bash
npm test              # Run tests
npm run typecheck     # Type checking
npm run lint          # Linting
npm run build         # Build
npm run validate      # All validation (typecheck + lint + test)
```

## Directory Structure

```
.claude/
├── claudesprint/
│   ├── config/       # notifications.json, models.json, hooks.json, project.json
│   ├── project/      # current_issue.json, current_issue.log (session data)
│   ├── prompts/      # PROMPT_*.md workflow prompts
│   ├── schemas/      # JSON schemas for validation
│   ├── specs/        # Specification files
│   └── sprints/      # Sprint files (one per spec)
└── CLAUDE.md
```

## CLI Commands

```bash
claudesprint status                    # Current workflow status
claudesprint init --spec SPEC_01.md    # Initialize sprint from spec
claudesprint run --sprint <path>       # Run workflow
claudesprint reset                     # Clear current issue state
claudesprint validate                  # Validate JSON files
```

## Session Workflow

### Get Bearings (FIRST every session)

```bash
pwd
cat .claude/claudesprint/project/current_issue.json
SPRINT_PATH=$(cat .claude/claudesprint/project/current_issue.json | jq -r '.sprint_path')
cat "$SPRINT_PATH"
git log --oneline -5 2>/dev/null || echo "Not a git repo"
tail -n 15 .claude/claudesprint/project/current_issue.log 2>/dev/null || echo "No log yet"
```

Then execute ONLY the `next_action` in `current_issue.json`.

### Session Rules

1. **ONLY use current_issue.json + sprint.json** - no other context
2. **Fail fast** - if required fields missing, stop and report
3. **Execute one step** - complete it, then update current_issue.json
4. **Log progress** - append to current_issue.log
5. **Validate before exit** - run `claudesprint validate`

### Clean Exit

1. Update `current_issue.json` with new `step`, `changes`, `commands_run`
2. Append to `current_issue.log`
3. Run `claudesprint validate`

## Critical Rules

### Context Rules
- `current_issue.json` + `sprint.json` are the ONLY context between sessions
- If required info missing, FAIL FAST

### Commit Rules
- Do NOT commit unless: implementation complete, tests pass, code review clean
- Use explicit file staging (not `git add -A`)

### Sprint Rules
- `sprint.json` issues are immutable contracts
- Only change `status` and `history` fields during implementation

### Scope Rules
- ONE issue per workflow cycle
- Exit after completing one issue for fresh context

### Implementation Guidelines

**DO:** Exactly what acceptance criteria specify, error handling, tests for AC

**DON'T:** Features not in AC, optimizations not requested, refactoring unrelated code, extra configurability, unnecessary documentation

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Validation failed | Run `claudesprint validate` to see details |
| Invalid step | Valid: `select-issue`, `read-docs`, `implement`, `write-tests`, `run-tests`, `fix-tests`, `browser-validation`, `code-review`, `fix-code-review-issues`, `update-docs`, `stage-changes`, `commit-changes` |
| Starting fresh | Run `claudesprint reset` |
| Stuck in loop | Check `current_failures` in current_issue.json |
