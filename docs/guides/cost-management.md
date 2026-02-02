# Cost Management

ClaudeSprint runs autonomous loops that consume API tokens. Use these strategies to control costs.

## Understanding Token Usage

Each workflow step creates a new Claude session:

| Step | Typical Tokens | Model |
|------|---------------|-------|
| `read-docs` | 5-15K | Sonnet |
| `implement` | 20-50K | Opus |
| `write-tests` | 10-20K | Sonnet |
| `run-tests` | 5-10K | Sonnet |
| `fix-tests` | 15-30K | Opus |
| `code-review` | 10-20K | Opus |
| `commit-changes` | 2-5K | Sonnet |

A typical issue uses **80-150K tokens**. Complex issues with multiple fix cycles can use more.

## Cost Control Strategies

### 1. Limit Iterations

Always start with limited iterations:

```bash
# Run at most 5 iterations
claudesprint run -n 5

# Then increase if needed
claudesprint run -n 20
```

### 2. Use Sonnet for Everything

For testing or simple projects:

```bash
CLAUDESPRINT_MODEL_OVERRIDE=sonnet claudesprint run
```

This reduces costs by ~80% but may require more fix cycles.

### 3. Configure Per-Step Models

Edit `.claudesprint/config/models.json`:

```json
{
  "default": "sonnet",
  "steps": {
    "implement": "opus",
    "code-review": "opus"
  }
}
```

Use Opus only where quality matters most.

### 4. Write Better Specs

Clearer specifications = fewer fix cycles = lower costs.

Bad spec (causes retries):
```markdown
### 1) Add user authentication
```

Good spec (executes cleanly):
```markdown
### 1) Add login endpoint
- POST /api/login accepts { email, password }
- Returns { token } on success (JWT, expires in 24h)
- Returns 401 with { error: "Invalid credentials" } on failure
- Use bcrypt for password verification
- Acceptance: `npm test -- --grep "login"` passes
```

### 5. Break Large Issues into Smaller Ones

Large issues = more context = more tokens.

Instead of one 50K token issue, create five 10K token issues.

### 6. Monitor the Dashboard

```bash
claudesprint run --dashboard
```

Watch for:
- Issues stuck in fix cycles
- High retry counts
- Steps taking unusually long

Stop early if something seems wrong:
```
Ctrl+C
```

### 7. Set Hard Limits

Use Anthropic's API settings to set spending limits:

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Set monthly spend limits
3. Configure alerts at thresholds

## Estimating Costs

Rough estimates per issue (varies by complexity):

| Model Config | Cost per Issue | Notes |
|--------------|---------------|-------|
| Default (mixed) | $0.50-2.00 | Opus for critical steps |
| All Sonnet | $0.10-0.50 | May need more retries |
| All Opus | $2.00-5.00 | Highest quality |

For a 10-issue sprint:
- Default config: ~$5-20
- All Sonnet: ~$1-5
- All Opus: ~$20-50

## When to Stop

Stop the workflow if you see:
- Same test failing 3+ times in a row
- Retry count exceeding 5
- Implementation going in wrong direction

```bash
# Stop current run
Ctrl+C

# Check status
claudesprint status

# Reset if needed
claudesprint reset
```

Then review the spec or fix issues manually.
