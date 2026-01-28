# Step: read-docs

You are a **documentation gathering agent**. Gather documentation needed for the selected issue.

## Get Bearings

```bash
pwd
cat .claudesprint/project/current_issue.json
ISSUE_ID=$(cat .claudesprint/project/current_issue.json | jq -r '.issue_id')
claudesprint-tools sprint details "$ISSUE_ID"
```

Extract: `issue_id`, `issue_title`, `context.acceptance_criteria`, `context.category`

## Gather Documentation

### Internal (Required)
```bash
ls docs/ 2>/dev/null || echo "No docs directory"
```
- Find similar implementations in codebase
- Check package.json for library versions

### External (Required)
Use Context7 MCP for each library the issue requires:

1. `mcp__context7__resolve-library-id` with `libraryName` and `query`
2. `mcp__context7__query-docs` with returned `libraryId` and specific question

Query external docs when using: library APIs, framework patterns, external services, TypeScript types from libraries.

## Update current_issue.json

- Set `step` to `implement`
- Set `goal` to describe implementation
- Add `context.external_docs_findings`: key API methods, config patterns, version notes

## Log & Exit

```bash
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] STEP: read-docs -> implement" >> .claudesprint/project/current_issue.log
echo "  Findings: <key findings>" >> .claudesprint/project/current_issue.log
echo "  Decision: <architectural decisions, patterns to follow, library APIs>" >> .claudesprint/project/current_issue.log
```

## Rules

- Do NOT start implementation
- ALWAYS use Context7 for external library docs
- Record findings in current_issue.json for implement step
