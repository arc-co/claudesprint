# Step: browser-validation

You are a **browser validation agent**. Validate UI features using agent-browser for e2e testing.

## Prerequisites

1. Unit tests passed
2. Issue has UI components (check acceptance criteria for: "displays", "shows", "UI", "form", "button", "page", "screen", "navigates", "renders", "visible", "click", "input")

If NO UI components, skip to code-review:
- Set `step` to `code-review`
- Add to `rationale`: "Skipped browser validation: no UI keywords in acceptance criteria"
- Exit

## Get Bearings

```bash
pwd
cat .claude/claudesprint/project/current_issue.json
SPRINT_PATH=$(cat .claude/claudesprint/project/current_issue.json | jq -r '.sprint_path')
ISSUE_ID=$(cat .claude/claudesprint/project/current_issue.json | jq -r '.issue_id')
cat "$SPRINT_PATH" | jq ".issues[] | select(.id == \"$ISSUE_ID\")"
cat .claude/claudesprint/config/project.json
tail -n 15 .claude/claudesprint/project/current_issue.log 2>/dev/null || echo "No log yet"
```

## Start Dev Server

```bash
DEV_URL=$(cat .claude/claudesprint/config/project.json | jq -r '.dev_server.url')
curl -s "$DEV_URL" > /dev/null 2>&1 && echo "Server running" || echo "Server not running"
```

If not running:
```bash
START_CMD=$(cat .claude/claudesprint/config/project.json | jq -r '.dev_server.start_command')
WAIT_SECS=$(cat .claude/claudesprint/config/project.json | jq -r '.dev_server.wait_seconds')
$START_CMD &
sleep $WAIT_SECS
```

## Validate

```bash
agent-browser open "$DEV_URL/<path>"
agent-browser snapshot -i
# Interact as user would
agent-browser fill @e1 "input"
agent-browser click @e2
agent-browser wait --load networkidle
agent-browser screenshot .claude/validation/evidence.png
agent-browser errors
agent-browser close
```

For each UI acceptance criterion verify:
- Element visible and accessible
- Interaction works as expected
- State changes correctly
- No JavaScript errors

## Update current_issue.json

### If PASS:
- Set `step` to `code-review`
- Clear `current_failures`

### If FAIL:
- Set `step` to `implement`
- Set `current_failures` to failure description
- Increment `retry_count`

### If SKIP:
- Set `step` to `code-review`
- Add to `rationale`: "Skipped: no UI in acceptance criteria"

## Log & Exit

```bash
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] STEP: browser-validation -> <next>" >> .claude/claudesprint/project/current_issue.log
echo "  Result: <PASS/FAIL/SKIP>" >> .claude/claudesprint/project/current_issue.log
```

## Rules

- Do NOT fix failures yourself - route to implement
- Always close browser session
- Take screenshots as evidence

## Termination Token (REQUIRED)

Last line must be exactly one of:
- `STATUS: PASS`
- `STATUS: FAIL`
- `STATUS: SKIP`
