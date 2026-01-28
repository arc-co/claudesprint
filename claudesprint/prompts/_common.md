# Common Prompt Patterns

Reference file for shared patterns used across workflow prompts.

## Context Rules

**ONLY** use `current_issue.json` and `sprint.json` as context. Do NOT infer or remember anything else. If required fields are missing, **FAIL FAST**.

## Get Bearings

```bash
pwd
cat .claudesprint/project/current_issue.json
ISSUE_ID=$(cat .claudesprint/project/current_issue.json | jq -r '.issue_id')
claudesprint-tools sprint details "$ISSUE_ID"
git log --oneline -5 2>/dev/null || echo "Not a git repo"
```

Note: The full session log is automatically injected into the context. Do NOT read it manually.

## Atomic Write Pattern

```bash
cat > .claudesprint/project/current_issue.json.tmp << 'EOF'
{...updated content...}
EOF
mv .claudesprint/project/current_issue.json.tmp .claudesprint/project/current_issue.json
```

## Log Progress

```bash
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] STEP: <from> -> <to>" >> .claudesprint/project/current_issue.log
echo "  <summary>" >> .claudesprint/project/current_issue.log
```

## Update current_issue.json

Required fields to update:
- `step` - next workflow step
- `goal` - 1-2 sentence goal description
- `next_action` - specific action for next session
- `changes` - array of `{path, summary}` for modified files
- `commands_run` - array of commands executed

Log key decisions to `current_issue.log` using the Log Progress pattern above.

## Termination Tags

Some steps require a status tag as the final output:
- `<status>pass</status>` - step succeeded
- `<status>fail</status>` / `<status>fail_code</status>` / `<status>fail_test</status>` - step failed
- `<status>skip</status>` - step skipped (not applicable)
- `<status>issues</status>` - issues found (code review)

## Session Rules

1. **ONLY use current_issue.json + sprint.json** - no other context
2. **Fail fast** - if required fields missing, stop and report
3. **Execute one step** - complete it, then update current_issue.json
4. **Log progress** - append to current_issue.log
5. **Validate before exit** - run `claudesprint validate`

## Critical Rules

### Commit Rules
- Do NOT commit unless: implementation complete, tests pass, code review clean
- Use explicit file staging (not `git add -A`)

### Sprint Rules
- `sprint.json` issues are immutable contracts
- Only change `status` and `history` fields during implementation

### Scope Rules
- ONE issue per workflow cycle
- Exit after completing one issue for fresh context

## Implementation Guidelines

**DO:** Exactly what acceptance criteria specify, error handling, tests for AC

**DON'T:** Features not in AC, optimizations not requested, refactoring unrelated code, extra configurability, unnecessary documentation

## Valid Steps

`select-issue`, `read-docs`, `implement`, `write-tests`, `run-tests`, `fix-tests`, `browser-validation`, `code-review`, `fix-code-review-issues`, `update-docs`, `stage-changes`, `commit-changes`
