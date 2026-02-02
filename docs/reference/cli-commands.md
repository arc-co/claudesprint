# CLI Reference

Complete reference for all ClaudeSprint commands.

## Global Options

```bash
claudesprint --version    # Show version
claudesprint --help       # Show help
```

## Getting Started

### doctor

Check environment and dependencies.

```bash
claudesprint doctor [--fix]
```

| Option | Description |
|--------|-------------|
| `--fix` | Auto-install missing optional packages |

Checks:
- Python version (3.10+ required)
- Claude CLI installed
- Claude CLI authenticated
- Optional: agent-browser, nicegui

### quickstart

Interactive project setup.

```bash
claudesprint quickstart [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--template` | Template: web-application, cli-tool, api-service, minimal |
| `--name` | Project name |
| `--description` | Project description |

### demo

Create and run a sample project.

```bash
claudesprint demo [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--dir` | Directory for demo project (default: `claudesprint-demo`) |
| `--clean` | Remove existing demo directory first |
| `--full` | Run complete workflow (not just setup) |
| `--skip-run` | Set up project but don't run workflow |
| `--dashboard` | Show real-time dashboard (default: on) |

## Workflow

### run

Execute the sprint workflow.

```bash
claudesprint run [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-n, --max-iterations` | Maximum iterations before stopping |
| `--sprint` | Path to sprint.json |
| `--spec` | Spec ID to run |
| `--dashboard` | Show real-time web dashboard |
| `-v, --verbose` | Increase output verbosity |

Examples:
```bash
# Run with 5 iteration limit
claudesprint run -n 5

# Run specific spec with dashboard
claudesprint run --spec SPEC_02 --dashboard

# Verbose output
claudesprint run -v
```

### status

Show current sprint status.

```bash
claudesprint status [--spec SPEC_ID]
```

Displays:
- Current sprint ID
- Issues completed/remaining
- Current issue and step
- Recent activity

### sprints

List all available sprints.

```bash
claudesprint sprints
```

### models

Show model configuration per step.

```bash
claudesprint models
```

## Setup

### init

Initialize sprint from specification.

```bash
claudesprint init [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--spec` | Specification file to use |
| `--update` | Update existing sprint (preserve completed) |

Examples:
```bash
# Initialize from spec
claudesprint init --spec SPEC_01.md

# Update existing sprint
claudesprint init --spec SPEC_01.md --update
```

### spec

Manage specifications.

```bash
claudesprint spec list           # List all specs
claudesprint spec show SPEC_ID   # Show spec content
claudesprint spec validate SPEC  # Validate spec format
```

## Utilities

### validate

Validate JSON artifacts.

```bash
claudesprint validate
```

Checks:
- `sprint.json` schema
- `current_issue.json` schema
- State consistency

### reset

Clear current issue state.

```bash
claudesprint reset [--hard]
```

| Option | Description |
|--------|-------------|
| `--hard` | Also clear sprint progress |

Use when:
- Stuck in a loop
- Want to restart current issue
- Need to clear corrupted state

### hook

Run ClaudeSprint hooks (internal use).

```bash
claudesprint hook --type TYPE
```

| Type | Purpose |
|------|---------|
| `server-guard` | Block hanging commands |
| `browser-guard` | Coordinate browser automation |
| `autonomous-continue` | Enable workflow continuation |

### config

Manage configuration.

```bash
claudesprint config show           # Show current config
claudesprint config set KEY VALUE  # Set config value
claudesprint config reset          # Reset to defaults
```

### features

Manage optional features.

```bash
claudesprint features list         # List available features
claudesprint features enable NAME  # Enable a feature
claudesprint features disable NAME # Disable a feature
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAUDESPRINT_MODEL_OVERRIDE` | Force model for all steps | - |
| `CLAUDESPRINT_MAX_RETRY` | Max retries per issue | 5 |
| `CLAUDESPRINT_LOG_LEVEL` | Log level | INFO |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (message displayed) |
