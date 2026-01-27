# Cost Management

ClaudeSprint uses Claude's API, which has usage-based pricing. This guide covers strategies to optimize costs while maintaining quality.

## Understanding Costs

### Model Pricing (Approximate)

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| Claude Opus | Higher | Higher |
| Claude Sonnet | Lower | Lower |

Opus is more capable but costs more. Sonnet is faster and cheaper but may produce lower quality for complex tasks.

### Where Tokens Are Spent

1. **System prompts**: CLAUDE.md, prompt files (~2-5K tokens per step)
2. **Context files**: current_issue.json, sprint.json (~1-3K tokens)
3. **Code reading**: Files read during implementation (~varies widely)
4. **Output**: Generated code, explanations (~varies by step)

### High-Cost Steps

| Step | Token Usage | Why |
|------|-------------|-----|
| `implement` | High | Reads codebase, generates code |
| `code-review` | High | Analyzes all changes, thorough review |
| `read-docs` | Medium-High | Explores codebase for context |
| `fix-tests` | Medium | Analyzes failures, may read files |
| `select-issue` | Low | Reads sprint.json, makes decision |
| `stage-changes` | Low | Just git commands |

## Model Selection Strategy

### Default Configuration

ClaudeSprint ships with an optimized model configuration:

```json
{
  "step_models": {
    "select-issue": "sonnet",
    "read-docs": "sonnet",
    "implement": "opus",
    "write-tests": "sonnet",
    "fix-tests": "opus",
    "browser-validation": "sonnet",
    "code-review": "opus",
    "fix-code-review-issues": "sonnet",
    "update-docs": "sonnet"
  }
}
```

### Rationale

**Use Opus for**:
- `implement`: Core code generation where quality matters most
- `fix-tests`: Nuanced judgment (code bug vs test bug)
- `code-review`: Critical quality gate, thoroughness matters
- `init`: One-time complex setup

**Use Sonnet for**:
- `select-issue`: Algorithmic selection, validated by later steps
- `read-docs`: Research that's validated by implementation
- `write-tests`: Pattern-based, failures caught by run-tests
- `update-docs`: Formulaic updates

### Cost vs Quality Trade-off

```
More Opus = Higher quality + Higher cost
More Sonnet = Lower cost + More retries

Sweet spot: Opus for judgment, Sonnet for pattern-following
```

## Cost Optimization Strategies

### 1. Minimize File Reading

The agent reads files to understand context. Reduce this by:

**In your spec, reference specific files**:
```markdown
### Technical Notes
- Follow pattern in `src/components/Button.tsx`
- Use types from `src/types/user.ts`
```

This prevents the agent from exploring the entire codebase.

### 2. Keep Issues Small

Large issues = more tokens for context.

**Instead of**:
```markdown
### Feature: Complete User Management
- User registration
- User login
- User profile
- Password reset
- Email verification
```

**Do this**:
```markdown
### Feature 1: User Registration
[specific criteria]

### Feature 2: User Login
[specific criteria]
```

### 3. Use Sonnet More Aggressively

For simpler projects, consider all-Sonnet:

```json
{
  "model_override": "sonnet"
}
```

Or selectively add Opus only where needed:

```json
{
  "default_model": "sonnet",
  "step_models": {
    "implement": "opus"
  }
}
```

### 4. Reduce Retries

Retries multiply costs. Reduce them by:

- Writing clearer acceptance criteria
- Providing more context in specs
- Fixing common failure patterns in your codebase

### 5. Skip Unnecessary Steps

Some steps can be skipped:

- `browser-validation`: Skip for API-only issues (auto-detected by category)
- `update-docs`: Skip for bugfixes (auto-detected)

### 6. Batch Similar Issues

Group related issues to maximize context reuse:

```markdown
### Feature 1: Add Button Component
### Feature 2: Add Card Component
### Feature 3: Add Modal Component
```

The agent learns component patterns once and applies them.

## Monitoring Costs

### Track Token Usage

The Claude API returns token counts. Track these over time:

```python
# Example logging in your integration
def log_usage(step, input_tokens, output_tokens):
    cost = calculate_cost(input_tokens, output_tokens)
    logger.info(f"{step}: {input_tokens}in + {output_tokens}out = ${cost:.4f}")
```

### Set Budgets

Use iteration limits to cap spending:

```bash
# Run max 10 iterations
claudesprint run -n 10
```

### Review After Sprints

After each sprint, review:
- Total tokens used
- Tokens per issue
- Retry count per issue
- Steps that consumed most tokens

## Cost Estimation

### Per-Issue Estimate

Rough estimate for a typical feature issue:

| Step | Input Tokens | Output Tokens |
|------|-------------|---------------|
| select-issue | 5K | 1K |
| read-docs | 10K | 2K |
| implement | 20K | 5K |
| write-tests | 10K | 3K |
| run-tests | 3K | 1K |
| code-review | 15K | 2K |
| update-docs | 5K | 2K |
| stage/commit | 3K | 1K |
| **Total** | **~70K** | **~17K** |

With retries, this could double. With complex issues, it could triple.

### Per-Sprint Estimate

For a 10-issue sprint:
- Best case: 10 × 87K = 870K tokens
- Typical case: 10 × 150K = 1.5M tokens (some retries)
- Worst case: 10 × 300K = 3M tokens (many retries)

## Budget-Constrained Workflows

### Low-Budget Mode

For cost-sensitive projects:

```json
{
  "model_override": "sonnet",
  "step_models": {
    "implement": "opus"  // Only Opus for code gen
  }
}
```

Combined with:
```bash
CLAUDESPRINT_MAX_RETRY=2 claudesprint run -n 5
```

### Medium-Budget Mode

Balanced approach (default config):

```json
{
  "step_models": {
    "implement": "opus",
    "fix-tests": "opus",
    "code-review": "opus"
  }
}
```

### High-Quality Mode

When correctness matters more than cost:

```json
{
  "model_override": "opus"
}
```

## ROI Considerations

### Cost of NOT Using Automation

Consider the alternative costs:
- Developer time for manual coding
- Debug time for subtle bugs
- Review time for code quality
- Test time for missing coverage

### Break-Even Analysis

If ClaudeSprint costs $50/sprint but saves 10 hours of developer time at $100/hour, the ROI is 20x.

### Quality Metrics

Track these to justify costs:
- Bugs found in code review
- Tests that catch regressions
- Time from spec to shipping
- Developer satisfaction

## Best Practices Summary

1. **Start with defaults**: The default model config is optimized
2. **Write precise specs**: Reduces context loading and retries
3. **Keep issues small**: Lower tokens per issue
4. **Monitor usage**: Track and review regularly
5. **Adjust based on data**: Use your metrics to tune model selection
6. **Set iteration limits**: Prevent runaway costs

## Next Steps

- [Configuration](./configuration.md): Configure model selection
- [Specifications and Scoping](./specifications-and-scoping.md): Write efficient specs
- [Advanced Workflows](./advanced-workflows.md): Parallel execution strategies
