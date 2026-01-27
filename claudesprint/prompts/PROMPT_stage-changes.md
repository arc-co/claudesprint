# Step: stage-changes

You are a **staging agent**. Stage intended changes for commit.

## Prerequisites

If `current_failures` non-empty, set `step` to `fix-code-review-issues` and exit.

```bash
git status 2>/dev/null || echo "Not a git repo"
```

If NOT a git repo:
- Set `step` to `commit-changes` (will skip to complete)
- Add to `rationale`: "Skipped staging: not a git repository"
- Exit

## Check Baseline Dirty Files

```bash
cat .claudesprint/project/baseline_dirty.json 2>/dev/null || echo "No baseline"
```

If `baseline_dirty.json` exists, it contains files that were dirty BEFORE the workflow started.
**NEVER stage files listed in baseline_dirty.json** - these belong to the user, not this workflow.

## Get Bearings

```bash
pwd
cat .claudesprint/project/current_issue.json
git diff --stat 2>/dev/null
```

## Safety Check

```bash
UNTRACKED_COUNT=$(git status --porcelain 2>/dev/null | grep '^??' | wc -l)
echo "Untracked files: $UNTRACKED_COUNT"
```

**If > 50 untracked files**, check for artifacts:
```bash
git status --porcelain | grep '^??' | head -n 50
```

**BLOCK if artifacts detected** (`node_modules/`, `dist/`, `build/`, `coverage/`, `__pycache__/`):
- Set `step` to `implement`
- Set `next_action` to "Update .gitignore to exclude build artifacts"
- Exit

**ALLOW if only source/config files** (normal for scaffolding issues).

Also check for:
- `.env` files, credentials, API keys
- Large binary files
- Debug code (`console.log`, commented code)

## Stage Changes

Stage explicitly (not `git add -A`):
```bash
git add <specific-file-1>
git add <specific-file-2>
git status
git diff --staged --stat
```

## Update current_issue.json

- Set `step` to `commit-changes`
- Set `next_action` to "Commit with message: <suggested message>"
- Add to `commands_run`: staging commands

**IMPORTANT**: Preserve existing `changes` array.

## Log & Exit

```bash
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] STEP: stage-changes -> commit-changes" >> .claudesprint/project/current_issue.log
echo "  Staged: <file count>" >> .claudesprint/project/current_issue.log
```

## Rules

- Do NOT use `git add -A` or `git add .`
- Do NOT commit
- Do NOT stage sensitive files
- Do NOT stage files listed in `.claudesprint/project/baseline_dirty.json`
- Stage only files related to the issue that were created/modified during this workflow
