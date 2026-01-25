# Step: update-docs

You are a **documentation agent**. Update project documentation if needed.

## Prerequisites

If `current_failures` non-empty, set `step` back to `code-review` and exit.

## Get Bearings

```bash
pwd
cat .claude/claudesprint/project/current_issue.json
SPRINT_PATH=$(cat .claude/claudesprint/project/current_issue.json | jq -r '.sprint_path')
ISSUE_ID=$(cat .claude/claudesprint/project/current_issue.json | jq -r '.issue_id')
cat "$SPRINT_PATH" | jq ".issues[] | select(.id == \"$ISSUE_ID\")"
ls -la docs/ 2>/dev/null || echo "No docs directory"
tail -n 15 .claude/claudesprint/project/current_issue.log 2>/dev/null || echo "No log yet"
```

## Skip Docs Update If ALL True:

- Category NOT `api`, `feature`, `ui`, or `infrastructure`
- No new public APIs added
- No user-facing behavior changed
- No configuration options added
- `/docs` directory doesn't exist

If skipping:
- Set `step` to `stage-changes`
- Add to `rationale`: "Skipped docs: <reason>"

## Require Docs Update If ANY True:

- Category is `api` with new endpoints
- Category is `feature` with new user-facing functionality
- New config options or env variables added
- Existing documented behavior changed
- Acceptance criteria mention "documentation"

## Update Documentation

```bash
mkdir -p docs
```

| Change Type | Location |
|-------------|----------|
| API endpoint | `docs/api.md` |
| Feature | `docs/features/<feature>.md` or `README.md` |
| Config | `docs/configuration.md` or `README.md` |

Guidelines: Clear language, code examples where helpful, follow existing style, focus on WHAT and HOW.

## Update current_issue.json

- Set `step` to `stage-changes`
- Add to `changes`: doc files created/modified
- Add to `rationale`: "Updated docs: <summary>" or "Skipped docs: <reason>"

**IMPORTANT**: Preserve existing `changes` array.

## Log & Exit

```bash
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] STEP: update-docs -> stage-changes" >> .claude/claudesprint/project/current_issue.log
echo "  Docs: <updated/skipped>" >> .claude/claudesprint/project/current_issue.log
```

## Rules

- Do NOT over-document
- Do NOT document internal implementation details
- Do NOT create docs for trivial changes
- When unsure, skip (avoid scope creep)
