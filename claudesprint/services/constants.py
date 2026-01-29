"""Constants for ClaudeSprint services."""

__all__ = ["PROMPTS_README_CONTENT", "CLAUDESPRINT_SKILL_CONTENT"]

# Content for the prompts README file
PROMPTS_README_CONTENT = """# Prompt Overrides

This directory allows you to customize ClaudeSprint prompts for your project.

## How It Works

To override a built-in prompt, create a file with the same name in this directory.
ClaudeSprint checks this directory first before falling back to built-in prompts.

## Available Prompts

- `PROMPT_init.xml.j2` - Sprint initialization from spec
- `PROMPT_plan.xml.j2` - Planning mode
- `PROMPT_select-issue.xml.j2` - Issue selection step
- `PROMPT_read-docs.xml.j2` - Documentation reading step
- `PROMPT_implement.xml.j2` - Implementation step
- `PROMPT_write-tests.xml.j2` - Test writing step
- `PROMPT_run-tests.xml.j2` - Test execution step
- `PROMPT_fix-tests.xml.j2` - Test fixing step
- `PROMPT_browser-validation.xml.j2` - Browser QA step
- `PROMPT_code-review.xml.j2` - Code review step
- `PROMPT_fix-code-review-issues.xml.j2` - Code review fixes
- `PROMPT_update-docs.xml.j2` - Documentation updates
- `PROMPT_stage-changes.xml.j2` - Stage changes step
- `PROMPT_commit-changes.xml.j2` - Commit changes step

## Example

To customize the implementation prompt:

1. Copy the built-in prompt (or create from scratch)
2. Save as `.claudesprint/prompts/PROMPT_implement.xml.j2`
3. ClaudeSprint will use your version instead

## Notes

- Keep the same structure and required sections
- Test changes with a single issue before using in production
- You can delete override files to revert to built-in behavior
"""

# Content for the ClaudeSprint skill file
CLAUDESPRINT_SKILL_CONTENT = """---
name: claudesprint
description: Orchestrates autonomous development sprints using ClaudeSprint. Use when the user needs to: initialize or run development sprints, manage sprint issues, track workflow progress, check sprint status, or coordinate multi-step autonomous development tasks.
allowed-tools: Bash(claudesprint:*)
---

# Autonomous Development with ClaudeSprint

## Quick start

```bash
claudesprint init --spec <spec_file>  # Create sprint from spec
claudesprint run                       # Run the sprint workflow
claudesprint status                    # Show current status
```

## Core workflow

ClaudeSprint uses a **dual-loop architecture**:

1. **Sprint Loop (outer)**: Manages issues from the sprint backlog
   - Selects next available issue
   - Tracks completion and progress
   - Handles sprint-level concerns (branching, PRs)

2. **Issue Loop (inner)**: Executes 13 workflow steps per issue
   - read-docs → explore → plan → implement → write-tests →
   - run-tests → fix-tests → browser-qa → fix-browser →
   - stage-changes → commit-changes → verify → complete

## Commands - Sprint Lifecycle

```bash
claudesprint init --spec <file>        # Initialize sprint from spec file
claudesprint init --spec SPEC_01       # Use spec from .claudesprint/specs/
claudesprint run                        # Run active sprint workflow
claudesprint run --spec SPEC_01         # Run specific sprint
claudesprint run -n 5                   # Limit to 5 iterations
claudesprint run --debug-conversations  # Log agent I/O for debugging
claudesprint run -v                     # Verbose output
claudesprint run -vv                    # Debug output
claudesprint status                     # Show sprint and issue status
claudesprint status --spec SPEC_01      # Status for specific sprint
claudesprint-tools sprints                    # List all available sprints
claudesprint validate                   # Validate sprint.json structure
claudesprint reset                      # Clear current issue state
```

## Commands - Planning

```bash
claudesprint plan                       # Run planning agent
claudesprint plan --spec SPEC_01        # Plan for specific spec
```

## Commands - Issue Management (agent tools)

These commands are used by agents during workflow execution:

```bash
# Get current issue state
claudesprint-tools issue get

# Initialize issue state
claudesprint-tools issue init <issue_id>
claudesprint-tools issue init ISSUE_01 --step implement
claudesprint-tools issue init ISSUE_01 --goal "Add login feature"

# Update issue fields
claudesprint-tools issue update --goal "New goal"
claudesprint-tools issue update --next-action "Write tests"

# Set next workflow step
claudesprint-tools issue step <step_name>
claudesprint-tools issue step implement --goal "Build feature"
claudesprint-tools issue step run-tests --clear-failures

# Record file changes
claudesprint-tools issue change <path> <summary>
claudesprint-tools issue change src/auth.py "Added login endpoint"

# Record failures
claudesprint-tools issue failure <message>
claudesprint-tools issue failure "Tests failed: 2 assertions"
claudesprint-tools issue failure "Timeout" --no-increment

# Clear failures and retry count
claudesprint-tools issue clear-failures
```

## Commands - Sprint Queries (agent tools)

Token-optimized queries for agents:

```bash
# List available issues (compact view)
claudesprint-tools sprint available
claudesprint-tools sprint available --spec SPEC_01

# Start working on an issue
claudesprint-tools sprint start <issue_id>
claudesprint-tools sprint start ISSUE_03 --spec SPEC_01

# Get full issue details
claudesprint-tools sprint details <issue_id>
claudesprint-tools sprint details ISSUE_03 --spec SPEC_01
```

## Commands - Configuration

```bash
# Global config file
claudesprint config path                # Show config file location
claudesprint config init                # Create default config
claudesprint config init --force        # Overwrite existing
claudesprint config show                # Display current settings
claudesprint config edit                # Open in $EDITOR

# Model configuration
claudesprint models                     # Show model per step
```

## Commands - Diagnostics

```bash
claudesprint doctor                     # Check environment and deps
claudesprint doctor -v                  # Verbose diagnostics
claudesprint doctor --fix               # Auto-fix issues
```

## Examples

### Full sprint workflow

```bash
# 1. Initialize repo (first time only)
claudesprint initrepo

# 2. Create spec file
# Write your spec to .claudesprint/specs/my-feature.md

# 3. Initialize sprint from spec
claudesprint init --spec my-feature.md

# 4. Run the sprint
claudesprint run

# 5. Monitor progress
claudesprint status
```

### Issue step progression

```bash
# Agent navigating through workflow steps
claudesprint-tools issue step read-docs --goal "Understand requirements"
claudesprint-tools issue step explore --goal "Map codebase structure"
claudesprint-tools issue step plan --goal "Design implementation"
claudesprint-tools issue step implement --goal "Write the feature"
claudesprint-tools issue step write-tests --goal "Add test coverage"
claudesprint-tools issue step run-tests
claudesprint-tools issue step stage-changes
claudesprint-tools issue step commit-changes
claudesprint-tools issue step complete
```

### Failure recovery

```bash
# Record a test failure
claudesprint-tools issue failure "AssertionError in test_login"

# Check current state
claudesprint-tools issue get

# After fixing, clear failures and continue
claudesprint-tools issue clear-failures
claudesprint-tools issue step run-tests
```

## Debugging

```bash
# Validate sprint structure
claudesprint validate

# Verbose logging
claudesprint run -v      # Verbose
claudesprint run -vv     # Debug level

# Log agent conversations
claudesprint run --debug-conversations
# Output written to agent_conversations.log

# Environment check
claudesprint doctor -v
```
"""
