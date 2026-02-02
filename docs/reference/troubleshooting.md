# Troubleshooting

Common issues and solutions.

## Installation Issues

### "Command not found: claudesprint"

The package isn't in your PATH.

**Solution:**
```bash
# Check if installed
pip show claudesprint

# If installed, find location
python -c "import claudesprint; print(claudesprint.__file__)"

# Reinstall with pipx for better PATH handling
pipx install claudesprint
```

### "Command not found: claude"

Claude Code CLI is not installed.

**Solution:**
1. Install from [official guide](https://docs.anthropic.com/en/docs/claude-code)
2. Verify: `claude --version`
3. Authenticate: `claude login`

### "Claude CLI not authenticated"

You need to log in.

**Solution:**
```bash
claude login
```

## Runtime Issues

### "current_issue.json validation failed"

The issue state file is corrupted or incomplete.

**Solution:**
```bash
# See what's wrong
claudesprint validate

# Reset the current issue
claudesprint reset
```

### Stuck in a loop

The workflow keeps retrying the same step.

**Diagnosis:**
```bash
# Check current state
claudesprint status

# View failure details
cat .claudesprint/project/current_issue.json | jq '.current_failures'
```

**Solutions:**
1. Check if tests are actually passing locally
2. Review the spec for ambiguous requirements
3. Reset and try again:
   ```bash
   claudesprint reset
   claudesprint run -n 3
   ```

### Max retry limit reached

Too many failed attempts on one issue.

**Solution:**
```bash
# Check what's failing
claudesprint status

# Increase limit temporarily
CLAUDESPRINT_MAX_RETRY=10 claudesprint run

# Or reset and fix manually
claudesprint reset
```

### Tests pass locally but fail in ClaudeSprint

Environment differences between your shell and Claude's session.

**Common causes:**
- Missing environment variables
- Different working directory
- Node modules not installed

**Solution:**
Ensure your test command works from project root:
```bash
cd /path/to/project
npm test  # Should work from here
```

Update hooks.json if needed:
```json
{
  "test": {
    "command": "cd /absolute/path && npm test",
    "timeout": 300
  }
}
```

## Browser Automation Issues

### "agent-browser not found"

Browser automation tool not installed.

**Solution:**
```bash
npm install -g agent-browser
agent-browser install  # Install browser deps
```

### Browser validation failing

Browser tests can't connect or interact.

**Solutions:**
1. Ensure dev server is running:
   ```bash
   npm run dev  # In another terminal
   ```

2. Check project config:
   ```json
   {
     "dev_server": {
       "url": "http://localhost:3000",
       "health_check": "/health"
     }
   }
   ```

3. Reinstall browser dependencies:
   ```bash
   agent-browser install --with-deps  # Linux
   agent-browser install              # macOS
   ```

## State Issues

### "Sprint file not found"

No sprint initialized for this project.

**Solution:**
```bash
# Initialize from spec
claudesprint init --spec SPEC_01.md

# Or check if spec exists
ls .claudesprint/specs/
```

### "Session lock held by another process"

Another ClaudeSprint instance is running.

**Solution:**
```bash
# Check for running processes
ps aux | grep claudesprint

# Remove stale lock (if no process running)
rm .claudesprint/state/session.lock
```

### Corrupted sprint.json

Sprint file is invalid JSON.

**Solution:**
```bash
# Validate
python -m json.tool .claudesprint/sprints/SPEC_01/sprint.json

# Re-initialize from spec
claudesprint init --spec SPEC_01.md
```

## Performance Issues

### Workflow running slowly

Each step takes too long.

**Diagnosis:**
- Check iteration count with `claudesprint status`
- Watch dashboard for bottlenecks

**Solutions:**
1. Use Sonnet for more steps:
   ```bash
   CLAUDESPRINT_MODEL_OVERRIDE=sonnet claudesprint run
   ```

2. Simplify test suite (faster feedback)

3. Break large issues into smaller ones

### High API costs

Using too many tokens.

**Solutions:**
1. Limit iterations:
   ```bash
   claudesprint run -n 5
   ```

2. Use cheaper models:
   ```bash
   CLAUDESPRINT_MODEL_OVERRIDE=sonnet claudesprint run
   ```

3. Write more specific specs (fewer retries)

## Getting Help

### Check environment

```bash
claudesprint doctor
```

### View logs

```bash
# Current issue log
cat .claudesprint/project/current_issue.log

# Run with verbose output
claudesprint run -v
```

### Report issues

Include:
- Output of `claudesprint doctor`
- Output of `claudesprint status`
- Contents of `current_issue.json` (sanitized)
- Steps to reproduce

Report at: [github.com/arc-co/claudesprint/issues](https://github.com/arc-co/claudesprint/issues)
