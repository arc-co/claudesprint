# CLI Commands

Complete reference for the `claudesprint` command-line interface.

## Command Overview

```bash
claudesprint <command> [options]
```

| Command | Description |
|---------|-------------|
| `doctor` | Diagnose environment and verify dependencies |
| `initrepo` | Initialize .claudesprint/ in a project |
| `status` | Show current workflow status |
| `init` | Initialize a sprint from a specification |
| `run` | Run the workflow loop |
| `plan` | Regenerate/update sprint from spec |
| `sprints` | List all available sprints |
| `reset` | Reset current issue state |
| `validate` | Validate state files against schemas |
| `models` | Show model configuration |
| `notify` | Send a manual notification |
| `config` | Manage global configuration |
| `hook` | Execute Claude hook handlers |

## doctor

Diagnose environment and verify all dependencies are correctly configured.

```bash
claudesprint doctor [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--verbose`, `-v` | Show detailed information for each check |
| `--fix` | Attempt to auto-fix issues (install missing packages) |

### Checks Performed

| Check | Required | Description |
|-------|----------|-------------|
| Python Version | Yes | Python 3.10 or higher |
| Required Packages | Yes | rich, typer, pydantic, httpx, jinja2 |
| Claude CLI | Yes | Claude Code CLI installed and accessible |
| Project Structure | No | .claudesprint/ directory exists |
| agent-browser | No | Browser automation for E2E testing |
| npm | No | Required for agent-browser installation |

### Output Example

```
ClaudeSprint Doctor

  ✓ Python Version: Python 3.11
  ✓ Required Packages: All required packages installed
  ✓ Claude CLI: Claude CLI installed
  ⚠ Project Structure: No .claudesprint/ directory found
  ⚠ agent-browser (optional): Not installed - Browser automation for E2E testing
  ✓ npm (optional): Required for agent-browser installation

✓ All required checks passed (2 warnings)
```

### Auto-Fix

The `--fix` flag attempts to install missing Python packages:

```bash
claudesprint doctor --fix
```

This will run `pip install` for any missing required packages.

## initrepo

Initialize .claudesprint/ directory in the current project.

```bash
claudesprint initrepo [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--force`, `-f` | Reinitialize even if .claudesprint/ exists |
| `--skip-hooks` | Skip injecting Claude hooks into .claude/settings.json |

### Behavior

1. Creates `.claudesprint/state/` for runtime state files
2. Creates `.claudesprint/prompts/` for custom prompt overrides
3. Adds `.claudesprint/` to `.gitignore`
4. Injects ClaudeSprint hooks into `.claude/settings.json`

### Output

```
✓ Initialized .claudesprint/ directory

Created directories:
  .claudesprint/state
  .claudesprint/prompts

✓ Claude hooks injected into .claude/settings.json

Next steps:
  1. Create a spec file in .claude/claudesprint/specs/
  2. Run: claudesprint init --spec <spec_file>
  3. Run: claudesprint run
```

## status

Display current workflow status including active issue, sprint progress, and retry count.

```bash
claudesprint status
```

### Output Example

```
ClaudeSprint Status
==================
Current Issue: feature-002 (Increment Button)
Step: run-tests
Retry Count: 0
Goal: Implement increment button that increases count by 1

Sprint: SPEC_01 (.claude/claudesprint/sprints/SPEC_01/sprint.json)
  Total Issues: 4
  Completed: 2
  In Progress: 1
  Pending: 1
  Blocked: 0
```

### No Active Issue

```
ClaudeSprint Status
==================
Current Issue: None

Sprint: SPEC_01
  Completed: 4/4

Sprint complete! All issues finished.
```

## init

Initialize a new sprint from a specification file.

```bash
claudesprint init --spec <spec_file> [options]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--spec <file>` | Yes | Specification file name (in specs/ directory) |
| `--force` | No | Overwrite existing sprint file |

### Examples

```bash
# Initialize from a spec
claudesprint init --spec SPEC_01.md

# Reinitialize (overwrite existing)
claudesprint init --spec SPEC_01.md --force
```

### Behavior

1. Reads specification from `.claude/claudesprint/specs/<spec_file>`
2. Creates git branch `sprint/<spec_id>` (if git repo)
3. Creates sprint file at `.claude/claudesprint/sprints/<spec_id>/sprint.json`
4. Parses spec into issues with acceptance criteria
5. Sets all issues to `pending` status

### Output

```
Initializing sprint from SPEC_01.md...
Created branch: sprint/SPEC_01
Created sprint file: .claude/claudesprint/sprints/SPEC_01/sprint.json

Sprint initialized with 4 issues:
  - setup-001: Project Setup (critical)
  - feature-001: Counter Display (high)
  - feature-002: Increment Button (high)
  - feature-003: Decrement Button (medium)

Run `claudesprint run` to start the workflow.
```

## run

Start the workflow loop to process issues.

```bash
claudesprint run [options]
```

### Options

| Option | Description |
|--------|-------------|
| `-n <count>`, `--max-iterations <count>` | Maximum iterations before stopping |
| `--sprint <path>` | Specific sprint file to run (default: auto-detect) |

### Examples

```bash
# Run until complete or blocked
claudesprint run

# Run maximum 10 iterations
claudesprint run -n 10

# Run specific sprint
claudesprint run --sprint .claude/claudesprint/sprints/SPEC_01/sprint.json
```

### Behavior

1. Loads current state (current_issue.json or selects new issue)
2. Executes current step in workflow
3. Updates state files
4. Repeats until:
   - All issues complete
   - Max iterations reached
   - Fatal error occurs
   - Max retry limit exceeded

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Sprint complete or max iterations reached |
| 1 | Error during execution |
| 2 | Max retry limit exceeded |
| 3 | Invalid state files |

## plan

Regenerate or update a sprint from its specification.

```bash
claudesprint plan --spec <spec_file>
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--spec <file>` | Yes | Specification file to reprocess |

### Behavior

1. Reads current sprint state
2. Compares with specification
3. Identifies gaps or changes
4. Updates sprint.json (preserving completed issues)

### Use Cases

- Spec changed after init
- Need to add new issues
- Want to reprioritize

### Example

```bash
# Update sprint with spec changes
claudesprint plan --spec SPEC_01.md
```

## sprints

List all available sprints.

```bash
claudesprint sprints [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--pending` | Show only sprints with pending issues |
| `--complete` | Show only completed sprints |
| `--first` | Output only the first matching sprint |

### Output

```
Available Sprints
=================

SPEC_01 - Counter Application
  Path: .claude/claudesprint/sprints/SPEC_01/sprint.json
  Status: In Progress (2/4 complete)
  Branch: sprint/SPEC_01

SPEC_02 - User Authentication
  Path: .claude/claudesprint/sprints/SPEC_02/sprint.json
  Status: Not Started (0/6 complete)
  Branch: sprint/SPEC_02
```

### Examples

```bash
# List all sprints
claudesprint sprints

# Find next sprint to work on
claudesprint sprints --pending --first

# Check for completed work
claudesprint sprints --complete
```

## reset

Clear current issue state to start fresh.

```bash
claudesprint reset [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--hard` | Also clear the activity log |

### Behavior

1. Deletes `current_issue.json`
2. Optionally clears `current_issue.log`
3. Does NOT modify `sprint.json`

### Use Cases

- Stuck in a loop
- Want to start over
- Corrupted state files

### Example

```bash
# Reset current issue
claudesprint reset

# Full reset including log
claudesprint reset --hard
```

## validate

Validate state files against JSON schemas.

```bash
claudesprint validate [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--fix` | Attempt to fix simple issues |

### Behavior

Validates:
1. `current_issue.json` syntax and schema
2. `sprint.json` syntax and schema
3. Cross-references (issue ID exists, etc.)

### Output (Success)

```
Validation Results
==================
✓ current_issue.json: Valid
✓ sprint.json: Valid
✓ Cross-references: Valid

All state files are valid.
```

### Output (Errors)

```
Validation Results
==================
✗ current_issue.json: Invalid
  - Missing required field: step
  - Invalid value for retry_count: expected number, got string

✓ sprint.json: Valid

Run `claudesprint reset` to clear invalid current issue state.
```

## models

Display model configuration for each workflow step.

```bash
claudesprint models
```

### Output

```
Model Configuration
==================
Default Model: opus
Override: None

Step Models:
  select-issue        : sonnet
  read-docs           : sonnet
  implement           : opus
  write-tests         : sonnet
  fix-tests           : opus
  browser-validation  : sonnet
  code-review         : opus
  fix-code-review-issues: sonnet
  update-docs         : sonnet

Special Steps:
  init                : opus
  plan                : sonnet

To override all steps: CLAUDESPRINT_MODEL_OVERRIDE=opus claudesprint run
```

## notify

Send a manual notification.

```bash
claudesprint notify <event> <message>
```

### Arguments

| Argument | Description |
|----------|-------------|
| `event` | Event type: `step`, `failure`, `rate_limit`, `exit` |
| `message` | Notification message |

### Examples

```bash
# Notify step completion
claudesprint notify step "Implement step completed successfully"

# Notify failure
claudesprint notify failure "Max retry limit reached on run-tests"

# Notify workflow exit
claudesprint notify exit "Sprint SPEC_01 complete"
```

### Behavior

Sends notification via configured channels (Bark, etc.). Only works if notifications are enabled in config.

## config

Manage global ClaudeSprint configuration settings.

```bash
claudesprint config <subcommand>
```

### Subcommands

| Subcommand | Description |
|------------|-------------|
| `path` | Show configuration file path |
| `init` | Create default configuration file |
| `show` | Display current configuration |
| `edit` | Open configuration in editor |

### Examples

```bash
# Show configuration file path
claudesprint config path

# Create default configuration
claudesprint config init

# Display current settings
claudesprint config show

# Edit configuration in default editor
claudesprint config edit
```

### Configuration File Location

The global configuration is stored at `~/.config/claudesprint/config.toml`.

### Configuration Keys

| Key | Type | Description |
|-----|------|-------------|
| `notifications.enabled` | bool | Enable/disable notifications |
| `notifications.bark.enabled` | bool | Enable Bark notifications |
| `notifications.bark.url` | string | Bark notification URL |
| `model_override` | string | Override model for all steps |

## hook

Execute Claude Code hook handlers. This command is typically called by Claude Code hooks configured in `.claude/settings.json`.

```bash
claudesprint hook --type <hook-type> [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--type <type>` | Hook type to execute (required) |
| `--input <json>` | JSON input from Claude Code hook system |

### Hook Types

| Type | Trigger | Purpose |
|------|---------|---------|
| `server-guard` | PreToolUse (Bash) | Blocks watch commands and interactive git operations |
| `browser-guard` | PreToolUse (Skill) | Coordinates browser automation resources |
| `autonomous-continue` | Stop | Controls autonomous workflow continuation |

### server-guard

Blocks commands that would hang or require interactive input:

- Watch commands: `npm run dev`, `yarn watch`, `nodemon`, etc.
- Interactive git: `git rebase -i`, `git add -i`, etc.
- Long-running processes that don't exit

### browser-guard

Manages browser automation:

- Prevents concurrent browser sessions
- Coordinates agent-browser resource access

### autonomous-continue

Controls whether Claude should continue working autonomously:

- Checks workflow step progression
- Manages retry limits
- Signals completion or continuation

### Output Format

Hooks return JSON for Claude Code:

```json
{
  "decision": "allow",
  "reason": null
}
```

Or to block:

```json
{
  "decision": "block",
  "reason": "Command would start a watch process"
}
```

### Example Hook Configuration

In `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "claudesprint hook --type server-guard",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAUDESPRINT_MODEL_OVERRIDE` | Force model for all steps | None |
| `CLAUDESPRINT_MAX_RETRY` | Maximum retries per step | 3 |
| `CLAUDESPRINT_LOG_LEVEL` | Logging verbosity | INFO |

### Examples

```bash
# Force Opus everywhere
CLAUDESPRINT_MODEL_OVERRIDE=opus claudesprint run

# Increase retry limit
CLAUDESPRINT_MAX_RETRY=5 claudesprint run

# Debug logging
CLAUDESPRINT_LOG_LEVEL=DEBUG claudesprint run
```

## Common Workflows

### New Sprint

```bash
# Create spec, then:
claudesprint init --spec MY_SPEC.md
claudesprint run
```

### Resume After Interruption

```bash
claudesprint status  # See where we are
claudesprint run     # Continue
```

### Fix Stuck Issue

```bash
claudesprint status  # Check current_failures
# Fix the issue manually
jq '.retry_count = 0' .claude/claudesprint/project/current_issue.json > tmp && mv tmp .claude/claudesprint/project/current_issue.json
claudesprint run
```

### Start Over

```bash
claudesprint reset
claudesprint run
```

### Full Reset

```bash
claudesprint reset --hard
rm .claude/claudesprint/sprints/SPEC_01/sprint.json
claudesprint init --spec SPEC_01.md
claudesprint run
```

## Exit Codes Summary

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | None needed |
| 1 | General error | Check output for details |
| 2 | Max retries exceeded | Fix issue, reset retry count |
| 3 | Invalid state | Run `claudesprint validate` |

## Next Steps

- [Schema Reference](./schema-reference.md): JSON schema details
- [Troubleshooting](./troubleshooting.md): Common issues and fixes
- [Configuration](../guides/configuration.md): Customize settings
