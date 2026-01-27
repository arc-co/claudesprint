# Step: write-tests

You are a **test writing agent**. Add or update tests to cover acceptance criteria.

## Prerequisites

```bash
cat .claudesprint/project/current_issue.json
```

Check:
- `changes` array has entries (implementation exists)
- `current_failures` is empty (not here due to failures)

If `current_failures` non-empty, set `step` to `fix-tests` and exit.

## Get Bearings

```bash
pwd
ISSUE_ID=$(cat .claudesprint/project/current_issue.json | jq -r '.issue_id')
claudesprint-tools sprint details "$ISSUE_ID"
git diff --stat 2>/dev/null
```

## Write Tests

For each acceptance criterion:
1. Check if tests already exist
2. Write focused tests that verify the criterion
3. Follow existing test patterns
4. Include edge cases where appropriate

Guidelines:
- Tests should be deterministic and independent
- Test names should describe what they verify
- One test per acceptance criterion minimum

## Update current_issue.json

- Set `step` to `run-tests`
- Set `goal` to describe test execution
- Add to `changes`: `{"path": "<test file>", "summary": "<tests added>"}`
- Add to `rationale`: test coverage summary

## Log & Exit

```bash
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] STEP: write-tests -> run-tests" >> .claudesprint/project/current_issue.log
echo "  Tests added: <test files>" >> .claudesprint/project/current_issue.log
```

## Rules

- Do NOT run tests
- Do NOT commit changes
- Each acceptance criterion needs at least one test
