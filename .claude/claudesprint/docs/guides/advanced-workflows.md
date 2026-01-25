# Advanced Workflows

This guide covers advanced patterns for using ClaudeSprint in complex scenarios: parallel execution, multiple sprints, integration with CI/CD, and team workflows.

## Parallel Sprint Execution

ClaudeSprint can run multiple sprints simultaneously by leveraging git branches. Since `init` creates a dedicated branch for each spec, you can run independent features in parallel.

### How Parallel Execution Works

```
main branch
    │
    ├── sprint/SPEC_01 ← Terminal 1 running claudesprint
    │
    ├── sprint/SPEC_02 ← Terminal 2 running claudesprint
    │
    └── sprint/SPEC_03 ← Terminal 3 running claudesprint
```

Each terminal:
- Works on its own branch
- Has its own `current_issue.json`
- Commits to its own branch
- Can be merged via PR when complete

### Setting Up Parallel Execution

**Terminal 1:**
```bash
# Initialize first sprint
claudesprint init --spec SPEC_01.md
claudesprint run
```

**Terminal 2:**
```bash
# Initialize second sprint
claudesprint init --spec SPEC_02.md
claudesprint run
```

### Managing State Across Terminals

Each sprint has its own state directory:
```
.claude/claudesprint/
├── sprints/
│   ├── SPEC_01/
│   │   └── sprint.json
│   └── SPEC_02/
│       └── sprint.json
└── project/
    └── current_issue.json  ← Shared! Only one active issue at a time
```

**Important**: The `current_issue.json` is shared. To run truly parallel sprints, you need separate working directories (git worktrees).

### Using Git Worktrees

For true parallelism:

```bash
# Create worktrees for each sprint
git worktree add ../project-spec01 sprint/SPEC_01
git worktree add ../project-spec02 sprint/SPEC_02

# Terminal 1
cd ../project-spec01
claudesprint run

# Terminal 2
cd ../project-spec02
claudesprint run
```

Each worktree has its own:
- Working directory
- `current_issue.json`
- Branch state

### Merging Completed Sprints

After sprints complete:

```bash
# Create PRs for each sprint branch
gh pr create --base main --head sprint/SPEC_01 --title "Feature: User Auth"
gh pr create --base main --head sprint/SPEC_02 --title "Feature: Shopping Cart"

# Review and merge
# Handle any conflicts manually
```

## Multi-Spec Projects

For large projects, break work into multiple specifications:

### Specification Strategy

```
.claude/claudesprint/specs/
├── SPEC_01_foundation.md      # Project setup, infrastructure
├── SPEC_02_auth.md            # Authentication system
├── SPEC_03_user_management.md # User CRUD
├── SPEC_04_products.md        # Product catalog
├── SPEC_05_cart.md            # Shopping cart
└── SPEC_06_checkout.md        # Checkout flow
```

### Dependency Order

Execute sprints in dependency order:

```bash
# Phase 1: Foundation
claudesprint init --spec SPEC_01_foundation.md
claudesprint run  # Wait for completion

# Phase 2: Core Features (can be parallel)
claudesprint init --spec SPEC_02_auth.md
claudesprint run

# Phase 3: Depends on auth
claudesprint init --spec SPEC_03_user_management.md
claudesprint run
```

### Tracking Cross-Spec Dependencies

In your specs, reference dependencies:

```markdown
# SPEC_03: User Management

## Prerequisites
- SPEC_01 (Foundation) completed
- SPEC_02 (Auth) completed

## Context
This spec builds on:
- Auth hooks from `src/hooks/useAuth.ts`
- API patterns from `src/api/auth.ts`
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: ClaudeSprint
on:
  workflow_dispatch:
    inputs:
      spec:
        description: 'Specification file'
        required: true
        default: 'SPEC_01.md'
      max_iterations:
        description: 'Max iterations'
        required: false
        default: '20'

jobs:
  sprint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install ClaudeSprint
        run: ./setup.sh --no-browser

      - name: Run Sprint
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          source .venv/bin/activate
          claudesprint init --spec ${{ inputs.spec }}
          claudesprint run -n ${{ inputs.max_iterations }}

      - name: Create PR
        if: success()
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          BRANCH=$(git branch --show-current)
          gh pr create --base main --head $BRANCH --title "Sprint: ${{ inputs.spec }}"
```

### Scheduled Sprints

Run sprints on a schedule:

```yaml
on:
  schedule:
    - cron: '0 2 * * 1'  # Every Monday at 2 AM

jobs:
  weekly-sprint:
    runs-on: ubuntu-latest
    steps:
      # ... setup steps ...
      - name: Run Weekly Sprint
        run: |
          source .venv/bin/activate
          # Find next pending spec
          NEXT_SPEC=$(claudesprint sprints --pending --first)
          if [ -n "$NEXT_SPEC" ]; then
            claudesprint init --spec "$NEXT_SPEC"
            claudesprint run -n 50
          fi
```

## Team Workflows

### Spec Review Process

Before running a sprint, have specs reviewed:

```markdown
## Spec Review Checklist

- [ ] Acceptance criteria are testable
- [ ] Dependencies are identified
- [ ] Technical context is complete
- [ ] Scope boundaries are clear
- [ ] Issues are appropriately sized
```

### Sprint Assignment

For teams, assign sprints to team members:

```bash
# Alice works on auth
git checkout -b sprint/SPEC_02_auth_alice
claudesprint init --spec SPEC_02_auth.md

# Bob works on products
git checkout -b sprint/SPEC_04_products_bob
claudesprint init --spec SPEC_04_products.md
```

### Code Review of Sprint Output

After a sprint completes:

1. Create PR from sprint branch to main
2. Review generated code as normal
3. Request changes if needed (manual fixes or new sprint)
4. Merge when approved

### Handling Conflicts

When parallel sprints create conflicts:

```bash
# On sprint branch
git fetch origin main
git merge origin/main

# Resolve conflicts manually
# Then continue or restart sprint
claudesprint run
```

## Recovery Scenarios

### Interrupted Sprint

If a sprint is interrupted (crash, network, etc.):

```bash
# Check current state
claudesprint status

# Resume from where it left off
claudesprint run

# Or reset and start fresh
claudesprint reset
claudesprint run
```

### Failed Sprint

If a sprint can't complete (blocked issue, max retries):

```bash
# Check what failed
cat .claude/claudesprint/project/current_issue.json | jq '.current_failures'

# Option 1: Fix manually and continue
# ... make manual fixes ...
jq '.retry_count = 0' .claude/claudesprint/project/current_issue.json > tmp && mv tmp .claude/claudesprint/project/current_issue.json
claudesprint run

# Option 2: Skip the issue
jq '.status = "blocked"' .claude/claudesprint/sprints/SPEC_01/sprint.json > tmp && mv tmp .claude/claudesprint/sprints/SPEC_01/sprint.json
claudesprint run

# Option 3: Reset and revise the spec
claudesprint reset
# ... update the spec ...
claudesprint init --spec SPEC_01.md
claudesprint run
```

### Corrupted State

If state files are corrupted:

```bash
# Validate and see errors
claudesprint validate

# Reset current issue state
claudesprint reset

# If sprint.json is corrupted, reinitialize
claudesprint init --spec SPEC_01.md --force
```

## Performance Optimization

### Warm-up Runs

For large codebases, do a warm-up run first:

```bash
# Run just the first issue to cache context
claudesprint run -n 3
```

### Selective Sprints

For minor changes, create focused specs:

```markdown
# SPEC_hotfix.md

## Overview
Quick fix for production bug.

## Issues

### Bugfix: Fix null pointer in checkout
- Handle null user gracefully
- Add unit test for null case

[Single issue, fast completion]
```

### Caching Strategies

Optimize for repeated patterns:

```markdown
## Technical Context

### Cached Patterns
These files demonstrate patterns already learned:
- Form handling: `src/components/forms/ExampleForm.tsx`
- API calls: `src/api/example.ts`
- Tests: `src/__tests__/example.test.ts`

Reference these instead of reading similar files.
```

## Monitoring and Observability

### Sprint Metrics

Track these metrics:

```bash
# Issues per sprint
jq '.metadata.total_issues' .claude/claudesprint/sprints/SPEC_01/sprint.json

# Completion rate
jq '.metadata | "\(.completed)/\(.total_issues)"' .claude/claudesprint/sprints/SPEC_01/sprint.json

# Average retries
# (calculated from history entries)
```

### Log Analysis

Analyze the activity log:

```bash
# Count step transitions
grep -c "→" .claude/claudesprint/project/current_issue.log

# Find failures
grep "FAIL" .claude/claudesprint/project/current_issue.log

# Track time per issue
grep "completed" .claude/claudesprint/project/current_issue.log
```

### Notification Alerts

Configure notifications for monitoring:

```json
{
  "enabled": true,
  "bark": {
    "enabled": true,
    "url": "https://api.day.app/YOUR_KEY"
  }
}
```

Get notified on:
- Step completions
- Failures
- Rate limits
- Sprint completion

## Next Steps

- [Configuration](./configuration.md): Fine-tune settings
- [Troubleshooting](../reference/troubleshooting.md): Handle edge cases
- [Cost Management](./cost-management.md): Optimize for scale
