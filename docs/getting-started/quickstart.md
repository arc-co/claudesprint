# Quickstart Guide

Get ClaudeSprint running in minutes.

## Option 1: Try the Demo

The fastest way to see ClaudeSprint in action:

```bash
claudesprint demo
```

This creates a sample project and builds a URL shortener application. Watch as ClaudeSprint:

1. Reads the specification
2. Implements features one by one
3. Writes and runs tests
4. Reviews code quality
5. Commits changes

The demo runs with `--dashboard` by default, showing real-time progress.

## Option 2: Interactive Setup

For your own project:

```bash
cd your-project
claudesprint quickstart
```

The quickstart wizard:

1. Checks prerequisites (Python, Claude CLI)
2. Creates `.claudesprint/` directory structure
3. Generates a project specification from a template
4. Initializes a sprint
5. Optionally starts the workflow

### Templates

Choose a template that matches your project:

- `web-application` - Full-stack web app
- `cli-tool` - Command-line application
- `api-service` - REST API backend
- `minimal` - Bare-bones starting point

## Option 3: Manual Setup

For full control over the process:

### 1. Initialize the Project

```bash
cd your-project
claudesprint init
```

This creates the `.claudesprint/` directory structure.

### 2. Create a Specification

Create a spec file in `.claudesprint/specs/`:

```markdown
# SPEC_01 - My Feature

## Purpose
What this feature delivers.

## Constraints
- Technical requirements
- What NOT to do

## Work Plan

### 1) First Issue
- Implementation details
- Acceptance criteria

### 2) Second Issue
- Implementation details
- Acceptance criteria

## Acceptance Checklist
- [ ] All tests pass
- [ ] Code reviewed
```

### 3. Initialize Sprint from Spec

```bash
claudesprint init --spec SPEC_01.md
```

This parses your specification and creates `sprint.json` with structured issues.

### 4. Run the Workflow

```bash
# Start with limited iterations (recommended)
claudesprint run -n 5

# Or run with dashboard
claudesprint run --dashboard
```

## Monitoring Progress

### Check Status

```bash
claudesprint status
```

Shows current sprint, active issue, and workflow step.

### View Dashboard

```bash
claudesprint run --dashboard
```

Opens a real-time web dashboard showing:

- Sprint progress
- Current issue and step
- Task board (pending/in-progress/completed)
- Live output

### List Sprints

```bash
claudesprint sprints
```

## Controlling Execution

### Limit Iterations

```bash
# Run at most 5 iterations
claudesprint run -n 5
```

### Resume After Stop

ClaudeSprint saves state automatically. Just run again:

```bash
claudesprint run
```

### Reset Current Issue

If stuck, reset the current issue state:

```bash
claudesprint reset
```

## Next Steps

- [Writing Specifications](../guides/specifications.md) - Craft effective specs
- [Configuration](../guides/configuration.md) - Customize behavior
- [Architecture](../concepts/architecture.md) - Understand how it works
