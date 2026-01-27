# Common Prompt Patterns

Reference file for shared patterns used across workflow prompts.

## Context Rules

**ONLY** use `current_issue.json` and `sprint.json` as context. Do NOT infer or remember anything else. If required fields are missing, **FAIL FAST**.

## Get Bearings

```bash
pwd
cat .claudesprint/project/current_issue.json
SPRINT_PATH=$(cat .claudesprint/project/current_issue.json | jq -r '.sprint_path')
cat "$SPRINT_PATH"
git log --oneline -5 2>/dev/null || echo "Not a git repo"
tail -n 15 .claudesprint/project/current_issue.log 2>/dev/null || echo "No log yet"
```

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
- `rationale` - array of key decisions made

## Termination Tokens

Some steps require a termination token as the last line:
- `STATUS: PASS` - step succeeded
- `STATUS: FAIL` / `STATUS: FAIL_CODE` / `STATUS: FAIL_TEST` - step failed
- `STATUS: SKIP` - step skipped (not applicable)
- `STATUS: ISSUES` - issues found (code review)
