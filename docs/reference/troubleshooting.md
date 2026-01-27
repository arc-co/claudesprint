# Troubleshooting

This guide covers common issues and their solutions when working with ClaudeSprint.

## Quick Diagnostic Commands

```bash
# Check current status
claudesprint status

# Validate state files
claudesprint validate

# View recent activity
tail -30 .claudesprint/project/current_issue.log

# Check current issue details
cat .claudesprint/project/current_issue.json | jq .

# Check sprint status
cat .claudesprint/sprints/SPEC_01/sprint.json | jq '.metadata'
```

## Common Issues

### "claudesprint: command not found"

**Cause**: Virtual environment not activated or package not installed.

**Solution**:
```bash
# Activate virtual environment
source .venv/bin/activate

# Verify installation
pip list | grep claudesprint

# Reinstall if needed
pip install -e .claudesprint/
```

### "current_issue.json validation failed"

**Cause**: State file is corrupted or has invalid values.

**Diagnosis**:
```bash
claudesprint validate
```

**Solution**:
```bash
# Reset to clean state
claudesprint reset

# Or fix specific field
jq '.step = "implement"' .claudesprint/project/current_issue.json > tmp && mv tmp .claudesprint/project/current_issue.json
```

### "Invalid step in current_issue.json"

**Cause**: Step field has invalid value.

**Valid Steps**:
- `select-issue`
- `read-docs`
- `implement`
- `write-tests`
- `run-tests`
- `fix-tests`
- `browser-validation`
- `code-review`
- `fix-code-review-issues`
- `update-docs`
- `stage-changes`
- `commit-changes`
- `complete-issue`

**Solution**:
```bash
# Set to valid step
jq '.step = "implement"' .claudesprint/project/current_issue.json > tmp && mv tmp .claudesprint/project/current_issue.json

# Or reset
claudesprint reset
```

### "MAX RETRY LIMIT REACHED"

**Cause**: Step failed repeatedly (default: 3 times).

**Diagnosis**:
```bash
cat .claudesprint/project/current_issue.json | jq '.current_failures'
```

**Solutions**:

1. **Fix the underlying issue**:
   ```bash
   # Read the failure message
   # Fix the code/test manually
   # Reset retry count
   jq '.retry_count = 0' .claudesprint/project/current_issue.json > tmp && mv tmp .claudesprint/project/current_issue.json
   claudesprint run
   ```

2. **Increase retry limit**:
   ```bash
   CLAUDESPRINT_MAX_RETRY=5 claudesprint run
   ```

3. **Skip the issue**:
   ```bash
   # Mark issue as blocked
   ISSUE_ID=$(cat .claudesprint/project/current_issue.json | jq -r '.issue_id')
   SPRINT=$(cat .claudesprint/project/current_issue.json | jq -r '.sprint_path')
   jq --arg id "$ISSUE_ID" '(.issues[] | select(.id == $id)).status = "blocked"' "$SPRINT" > tmp && mv tmp "$SPRINT"
   claudesprint reset
   claudesprint run
   ```

### "Sprint file not found"

**Cause**: Referenced sprint.json doesn't exist.

**Solution**:
```bash
# List available sprints
claudesprint sprints

# Initialize if needed
claudesprint init --spec SPEC_01.md
```

### "Issue ID not found in sprint"

**Cause**: current_issue.json references non-existent issue.

**Solution**:
```bash
# Check sprint for valid IDs
cat .claudesprint/sprints/SPEC_01/sprint.json | jq '.issues[].id'

# Reset to pick valid issue
claudesprint reset
claudesprint run
```

### Stuck in a Loop

**Symptoms**: Workflow keeps returning to the same step.

**Diagnosis**:
```bash
# Check retry count
cat .claudesprint/project/current_issue.json | jq '.retry_count'

# Check failures
cat .claudesprint/project/current_issue.json | jq '.current_failures'

# Check recent log
tail -30 .claudesprint/project/current_issue.log
```

**Solutions**:

1. **Clear failures and retry**:
   ```bash
   jq '.current_failures = "" | .retry_count = 0' .claudesprint/project/current_issue.json > tmp && mv tmp .claudesprint/project/current_issue.json
   claudesprint run
   ```

2. **Force to next step**:
   ```bash
   jq '.step = "write-tests"' .claudesprint/project/current_issue.json > tmp && mv tmp .claudesprint/project/current_issue.json
   claudesprint run
   ```

3. **Reset and start fresh**:
   ```bash
   claudesprint reset
   claudesprint run
   ```

### Tests Failing Repeatedly

**Cause**: Implementation or tests have bugs.

**Diagnosis**:
```bash
# Run tests manually
npm run validate

# Check what the agent thinks is wrong
cat .claudesprint/project/current_issue.json | jq '.current_failures'
```

**Solutions**:

1. **Check if tests match spec**:
   - Read acceptance criteria in sprint.json
   - Verify tests are testing the right things
   - Fix tests if they're wrong

2. **Check if code is correct**:
   - Read implementation
   - Verify it matches acceptance criteria
   - Fix code if it's wrong

3. **Manual intervention**:
   ```bash
   # Fix code/tests manually
   # Clear failures
   jq '.current_failures = "" | .retry_count = 0' .claudesprint/project/current_issue.json > tmp && mv tmp .claudesprint/project/current_issue.json
   claudesprint run
   ```

### Browser Validation Failing

**Cause**: Dev server not running, wrong URL, or UI not as expected.

**Diagnosis**:
```bash
# Check dev server config
cat .claudesprint/config/project.json

# Start dev server manually
npm run dev

# Test agent-browser
agent-browser open http://localhost:3000
agent-browser snapshot
agent-browser close
```

**Solutions**:

1. **Fix dev server URL**:
   ```json
   {
     "dev_server": {
       "url": "http://localhost:3000",
       "start_command": "npm run dev",
       "wait_seconds": 10
     }
   }
   ```

2. **Skip browser validation**:
   ```bash
   jq '.step = "code-review"' .claudesprint/project/current_issue.json > tmp && mv tmp .claudesprint/project/current_issue.json
   claudesprint run
   ```

### Git Errors

**Cause**: Git operations failed.

**Common Issues**:

1. **Not a git repo**:
   - Git steps are skipped automatically
   - This is not an error

2. **Merge conflicts**:
   ```bash
   # Resolve manually
   git status
   # Fix conflicts
   git add <files>
   git commit
   claudesprint run
   ```

3. **Detached HEAD**:
   ```bash
   git checkout sprint/SPEC_01
   claudesprint run
   ```

### Rate Limiting

**Symptoms**: "Rate limit exceeded" errors from Claude API.

**Solutions**:

1. **Wait and retry**:
   ```bash
   # Wait 1 minute
   sleep 60
   claudesprint run
   ```

2. **Use lower-cost model**:
   ```bash
   CLAUDESPRINT_MODEL_OVERRIDE=sonnet claudesprint run
   ```

3. **Reduce iterations**:
   ```bash
   claudesprint run -n 5
   ```

### Out of Memory

**Symptoms**: Process killed, system becomes unresponsive.

**Solutions**:

1. **Reduce test parallelism**:
   ```json
   {
     "test": {
       "command": "npm test -- --maxWorkers=2"
     }
   }
   ```

2. **Skip heavy validations temporarily**:
   ```json
   {
     "validate": {
       "command": "npm run lint && npm run typecheck"
     }
   }
   ```

## Recovery Procedures

### Full Reset

When nothing else works:

```bash
# 1. Save any work
git stash

# 2. Reset all state
claudesprint reset --hard

# 3. Check sprint status
cat .claudesprint/sprints/SPEC_01/sprint.json | jq '.metadata'

# 4. Start fresh
claudesprint run
```

### Reinitialize Sprint

If sprint.json is corrupted:

```bash
# 1. Backup completed issues
cat .claudesprint/sprints/SPEC_01/sprint.json | jq '.issues[] | select(.status == "completed")' > completed.json

# 2. Reinitialize
claudesprint init --spec SPEC_01.md --force

# 3. Mark completed issues (manually)
# Edit sprint.json to restore completed status
```

### Restore from Backup

If state files were accidentally deleted:

```bash
# Check if backup exists
ls -la .claudesprint/project/*.bak

# Restore
cp .claudesprint/project/current_issue.json.bak .claudesprint/project/current_issue.json
```

## Debug Mode

For detailed logging:

```bash
CLAUDESPRINT_LOG_LEVEL=DEBUG claudesprint run
```

This shows:
- All API calls
- State transitions
- Command outputs
- Decision points

## Getting Help

If you're still stuck:

1. **Check the logs**:
   ```bash
   tail -100 .claudesprint/project/current_issue.log
   ```

2. **Export diagnostic info**:
   ```bash
   claudesprint status > diagnostics.txt
   claudesprint validate >> diagnostics.txt
   cat .claudesprint/project/current_issue.json >> diagnostics.txt
   cat .claudesprint/sprints/SPEC_01/sprint.json | jq '.metadata' >> diagnostics.txt
   ```

3. **Report issue** at the project repository with:
   - Steps to reproduce
   - Diagnostic info
   - Expected vs actual behavior

## Next Steps

- [CLI Commands](./cli-commands.md): Command reference
- [Schema Reference](./schema-reference.md): State file formats
- [Configuration](../guides/configuration.md): Tune settings
