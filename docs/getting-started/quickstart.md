# Quickstart

This guide walks you through running ClaudeSprint from zero to a completed sprint. You'll see the orchestrator in action - autonomously selecting issues, implementing features, running tests, and committing code.

## Prerequisites

Ensure you have ClaudeSprint installed:

```bash
claudesprint doctor
```

If any required checks fail, see the [Installation Guide](./installation.md).

## Step 1: Initialize a Project

Navigate to your project directory and initialize ClaudeSprint:

```bash
cd your-project
claudesprint initrepo
```

This creates the `.claudesprint/` directory and configures Claude Code hooks.

## Step 2: Create or Use a Spec

ClaudeSprint works from specification files. You can use the included demo or create your own.

### Option A: Use the Demo Spec

Copy the textbook exchange demo spec:

```bash
mkdir -p .claude/claudesprint/specs
cat > .claude/claudesprint/specs/SPEC_01.md << 'EOF'
# SPEC 01 - Counter App

## Purpose
A simple counter application to demonstrate ClaudeSprint.

## Constraints
- Use vanilla TypeScript
- No external UI frameworks

## Work Plan

### 1) Project Setup
- Initialize npm project
- Configure TypeScript
- Create basic HTML structure

### 2) Counter Display
- Display current count
- Center on page

### 3) Increment Button
- Add button to increase count
- Update display on click

### 4) Decrement Button
- Add button to decrease count
- Prevent negative values

## Acceptance Checklist
- [ ] Counter displays current value
- [ ] Increment button increases count
- [ ] Decrement button decreases count
- [ ] Count cannot go below zero
EOF
```

### Option B: Write Your Own Spec

Create a spec file in `.claude/claudesprint/specs/` following this structure:

```markdown
# SPEC 01 - Feature Name

## Purpose
What this spec delivers.

## Constraints
- Technical constraints
- What NOT to do

## Work Plan
### 1) First milestone
- Task details
- Acceptance criteria

### 2) Second milestone
...

## Acceptance Checklist
- [ ] Criterion 1
- [ ] Criterion 2
```

## Step 3: Initialize a Sprint

```bash
claudesprint init --spec SPEC_01.md
```

This creates:
- A git branch: `sprint/SPEC_01`
- A sprint file with issues derived from the spec

Inspect the generated sprint:

```bash
claudesprint status
```

## Step 4: Run the Sprint

Start the autonomous workflow:

```bash
claudesprint run
```

The orchestrator will:
1. **Select an issue** based on priority and dependencies
2. **Read documentation** for relevant context
3. **Implement** the feature with minimal code changes
4. **Write tests** for acceptance criteria
5. **Run tests** and fix any failures
6. **Browser validation** (if UI-related)
7. **Code review** against the specification
8. **Commit changes** after all gates pass
9. **Mark complete** and select the next issue

### Watching Progress

In a separate terminal, you can watch the workflow:

```bash
# Watch the log
tail -f .claudesprint/state/current_issue.log

# Check current status
watch -n 5 claudesprint status
```

### Limiting Iterations

To run a specific number of iterations (useful for testing):

```bash
# Run up to 10 iterations then stop
claudesprint run -n 10
```

## Step 5: Monitor and Intervene

### Check Status

```bash
claudesprint status
```

Example output:
```
ClaudeSprint Status
==================
Current Issue: feature-002 (Increment Button)
Step: run-tests
Retry Count: 0

Sprint: SPEC_01
  Completed: 2/4
  In Progress: 1
  Pending: 1
```

### Pause the Workflow

The workflow respects Ctrl+C. It will finish the current step and exit cleanly. Resume with:

```bash
claudesprint run
```

### Reset and Start Fresh

If something goes wrong:

```bash
# Reset current issue state
claudesprint reset

# The sprint file is preserved; only the current issue context is cleared
claudesprint status
```

## Step 6: Review Completed Work

After issues complete, review what was built:

```bash
# See recent commits
git log --oneline -10

# See all changes since sprint started
git diff main..sprint/SPEC_01

# Run the application (if applicable)
npm run dev
```

## Common Scenarios

### Test Failures

If tests fail, the workflow automatically:
1. Analyzes whether it's a code bug or test bug
2. Routes to `fix-tests` or back to `implement`
3. Retries up to the max retry limit

### Code Review Issues

If code review finds problems, the workflow:
1. Routes to `fix-code-review-issues`
2. Makes targeted fixes
3. Re-runs tests
4. Returns to code review

### Max Retry Exceeded

If the workflow hits the retry limit:

```bash
# Check what failed
claudesprint status

# Fix the issue manually, then reset retry count
# Edit .claudesprint/state/current_issue.json and set retry_count to 0

# Continue
claudesprint run
```

## Quick Reference

```bash
# Verify environment
claudesprint doctor

# Initialize project
claudesprint initrepo

# Initialize a sprint from a spec
claudesprint init --spec SPEC_01.md

# Run the workflow
claudesprint run

# Limit iterations
claudesprint run -n 10

# Check status
claudesprint status

# View sprints
claudesprint sprints

# Reset current issue
claudesprint reset

# Validate state files
claudesprint validate

# View model configuration
claudesprint models
```

## What's Next?

You've now seen ClaudeSprint autonomously build an application. For your own projects:

1. **[Specifications and Scoping](../guides/specifications-and-scoping.md)**: Write effective specs that guide the agent
2. **[Configuration](../guides/configuration.md)**: Customize hooks, models, and settings
3. **[Prompt Customization](../guides/prompt-customization.md)**: Tailor agent behavior to your standards
4. **[Architecture](../concepts/architecture.md)**: Understand the dual-loop system in depth
