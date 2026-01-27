# Step: implement

You are a **coding agent**. Make minimal changes to implement the selected issue.

## Get Bearings

```bash
pwd
cat .claudesprint/project/current_issue.json
SPRINT_PATH=$(cat .claudesprint/project/current_issue.json | jq -r '.sprint_path')
cat "$SPRINT_PATH"
git log --oneline -5 2>/dev/null || echo "Not a git repo"
tail -n 15 .claudesprint/project/current_issue.log 2>/dev/null || echo "No log yet"
```

Extract: `issue_id`, `issue_title`, `context.acceptance_criteria`, `current_failures`, `rationale`

If `issue_id` is empty, report the issue.

## Implement

1. Check existing code first - don't assume something isn't implemented
2. Make minimal changes for acceptance criteria only
3. Follow existing patterns in codebase
4. Do NOT run tests yet

### Fix Mode (when `current_failures` non-empty)

If routed here from `run-tests`, `fix-tests`, or `browser-validation`:
- Read `current_failures` for specific issue to fix
- Focus on fixing that issue first
- Add rationale for fix approach

## Update current_issue.json

- Set `step` to `write-tests`
- Set `goal` to describe test writing
- Add to `changes`: `{"path": "<file>", "summary": "<what changed>"}`
- Add to `rationale`: key implementation decisions
- Clear `current_failures` if fixed

## Log & Exit

```bash
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] STEP: implement -> write-tests" >> .claudesprint/project/current_issue.log
echo "  Changes: <files modified>" >> .claudesprint/project/current_issue.log
```

## Rules

- Do NOT commit changes
- Do NOT run tests
- Do NOT mark issue complete
- Leave working tree dirty
