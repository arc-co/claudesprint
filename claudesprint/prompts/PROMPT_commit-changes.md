# Step: commit-changes

You are a **commit agent**. Commit staged changes with a clear message.

## Prerequisites

```bash
git status 2>/dev/null || echo "Not a git repo"
git diff --staged --stat 2>/dev/null || echo "Nothing staged"
```

If NOT a git repo or nothing staged:
- Set `step` to `select-issue` (issue complete, select next)
- Log: "Skipped commit: <reason>"
- Exit

## Get Bearings

```bash
pwd
cat .claudesprint/project/current_issue.json
```

Extract: `issue_id`, `issue_title`, `changes`

## Verify & Commit

1. Review `git diff --staged --stat`
2. Ensure correct files staged

```bash
git commit -m "<type>: <description>

- <detail 1>
- <detail 2>

Issue: <issue_id>"
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

```bash
git log --oneline -3
```

## Update sprint.json

Mark issue as completed:
1. Change `status` to `completed`
2. Add to `history`: `{"timestamp": "<ISO>", "action": "completed", "session_id": "<id>"}`
3. Update `metadata` counts

## Update current_issue.json

- Set `step` to `select-issue`
- Set `repo_state.git_head` to new SHA
- Set `repo_state.dirty` to `false`
- Clear `changes` array (now in git)
- Set `goal` to "Select next issue from sprint"
- Set `next_action` to "Run select-issue to pick next issue"
- Add to `commands_run`: commit command

## Log & Exit

```bash
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] STEP: commit-changes -> select-issue (ISSUE COMPLETE)" >> .claudesprint/project/current_issue.log
echo "  Commit: <short SHA>" >> .claudesprint/project/current_issue.log
echo "  Completed: <issue_id> - <issue_title>" >> .claudesprint/project/current_issue.log
```

## Rules

- Do NOT push to remote
- Do NOT amend previous commits
- Use clear, descriptive commit messages
