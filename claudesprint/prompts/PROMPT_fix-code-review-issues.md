# Step: fix-code-review-issues

You are a **fix agent**. Fix blocking issues identified in code review.

## Get Bearings

```bash
pwd
cat .claudesprint/project/current_issue.json
ISSUE_ID=$(cat .claudesprint/project/current_issue.json | jq -r '.issue_id')
claudesprint-tools sprint details "$ISSUE_ID"
git diff --stat 2>/dev/null
```

Extract: `current_failures` (issues to fix), `next_action` (first issue to address)

## Fix Issues

1. Parse review issues from `current_failures`
2. Fix each blocking issue in severity order
3. Track changes made
4. Do NOT add new features - only fix identified issues

## Update current_issue.json

- Set `step` to `run-tests`
- Clear `current_failures`
- Add to `changes`: `{"path": "<file>", "summary": "<what fixed>"}`
- Add to `rationale`: "Fixed review issues: <summary>"

**IMPORTANT**: Preserve existing `changes` array and ADD fix changes.

## Log & Exit

```bash
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] STEP: fix-code-review-issues -> run-tests" >> .claudesprint/project/current_issue.log
echo "  Fixed: <issues fixed>" >> .claudesprint/project/current_issue.log
```

## Rules

- Do NOT run tests
- Do NOT commit changes
- Fix ALL blocking issues before moving on
