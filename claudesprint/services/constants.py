"""Constants for ClaudeSprint services."""

__all__ = ["PROMPTS_README_CONTENT", "CLAUDESPRINT_SKILL_CONTENT", "AGENT_BROWSER_SKILL_CONTENT"]

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

# Content for the agent-browser skill file
AGENT_BROWSER_SKILL_CONTENT = """---
name: agent-browser
description: Automates browser interactions for web testing, form filling, screenshots, and data extraction. Use when the user needs to navigate websites, interact with web pages, fill forms, take screenshots, test web applications, or extract information from web pages.
allowed-tools: Bash(agent-browser:*)
---

# Browser Automation with agent-browser

## Quick start

```bash
agent-browser open <url>        # Navigate to page
agent-browser snapshot -i       # Get interactive elements with refs
agent-browser click @e1         # Click element by ref
agent-browser fill @e2 "text"   # Fill input by ref
agent-browser close             # Close browser
```

## Core workflow

1. Navigate: `agent-browser open <url>`
2. Snapshot: `agent-browser snapshot -i` (returns elements with refs like `@e1`, `@e2`)
3. Interact using refs from the snapshot
4. Re-snapshot after navigation or significant DOM changes

## Commands

### Navigation
```bash
agent-browser open <url>      # Navigate to URL
agent-browser back            # Go back
agent-browser forward         # Go forward
agent-browser reload          # Reload page
agent-browser close           # Close browser
```

### Snapshot (page analysis)
```bash
agent-browser snapshot            # Full accessibility tree
agent-browser snapshot -i         # Interactive elements only (recommended)
agent-browser snapshot -c         # Compact output
agent-browser snapshot -d 3       # Limit depth to 3
agent-browser snapshot -s "#main" # Scope to CSS selector
```

### Interactions (use @refs from snapshot)
```bash
agent-browser click @e1           # Click
agent-browser dblclick @e1        # Double-click
agent-browser focus @e1           # Focus element
agent-browser fill @e2 "text"     # Clear and type
agent-browser type @e2 "text"     # Type without clearing
agent-browser press Enter         # Press key
agent-browser press Control+a     # Key combination
agent-browser keydown Shift       # Hold key down
agent-browser keyup Shift         # Release key
agent-browser hover @e1           # Hover
agent-browser check @e1           # Check checkbox
agent-browser uncheck @e1         # Uncheck checkbox
agent-browser select @e1 "value"  # Select dropdown
agent-browser scroll down 500     # Scroll page
agent-browser scrollintoview @e1  # Scroll element into view
agent-browser drag @e1 @e2        # Drag and drop
agent-browser upload @e1 file.pdf # Upload files
```

### Get information
```bash
agent-browser get text @e1        # Get element text
agent-browser get html @e1        # Get innerHTML
agent-browser get value @e1       # Get input value
agent-browser get attr @e1 href   # Get attribute
agent-browser get title           # Get page title
agent-browser get url             # Get current URL
agent-browser get count ".item"   # Count matching elements
agent-browser get box @e1         # Get bounding box
```

### Check state
```bash
agent-browser is visible @e1      # Check if visible
agent-browser is enabled @e1      # Check if enabled
agent-browser is checked @e1      # Check if checked
```

### Screenshots & PDF
```bash
agent-browser screenshot          # Screenshot to stdout
agent-browser screenshot path.png # Save to file
agent-browser screenshot --full   # Full page
agent-browser pdf output.pdf      # Save as PDF
```

### Video recording
```bash
agent-browser record start ./demo.webm    # Start recording (uses current URL + state)
agent-browser click @e1                   # Perform actions
agent-browser record stop                 # Stop and save video
agent-browser record restart ./take2.webm # Stop current + start new recording
```
Recording creates a fresh context but preserves cookies/storage from your session. If no URL is provided, it automatically returns to your current page. For smooth demos, explore first, then start recording.

### Wait
```bash
agent-browser wait @e1                     # Wait for element
agent-browser wait 2000                    # Wait milliseconds
agent-browser wait --text "Success"        # Wait for text
agent-browser wait --url "**/dashboard"    # Wait for URL pattern
agent-browser wait --load networkidle      # Wait for network idle
agent-browser wait --fn "window.ready"     # Wait for JS condition
```

### Mouse control
```bash
agent-browser mouse move 100 200      # Move mouse
agent-browser mouse down left         # Press button
agent-browser mouse up left           # Release button
agent-browser mouse wheel 100         # Scroll wheel
```

### Semantic locators (alternative to refs)
```bash
agent-browser find role button click --name "Submit"
agent-browser find text "Sign In" click
agent-browser find label "Email" fill "user@test.com"
agent-browser find first ".item" click
agent-browser find nth 2 "a" text
```

### Browser settings
```bash
agent-browser set viewport 1920 1080      # Set viewport size
agent-browser set device "iPhone 14"      # Emulate device
agent-browser set geo 37.7749 -122.4194   # Set geolocation
agent-browser set offline on              # Toggle offline mode
agent-browser set headers '{"X-Key":"v"}' # Extra HTTP headers
agent-browser set credentials user pass   # HTTP basic auth
agent-browser set media dark              # Emulate color scheme
```

### Cookies & Storage
```bash
agent-browser cookies                     # Get all cookies
agent-browser cookies set name value      # Set cookie
agent-browser cookies clear               # Clear cookies
agent-browser storage local               # Get all localStorage
agent-browser storage local key           # Get specific key
agent-browser storage local set k v       # Set value
agent-browser storage local clear         # Clear all
```

### Network
```bash
agent-browser network route <url>              # Intercept requests
agent-browser network route <url> --abort      # Block requests
agent-browser network route <url> --body '{}'  # Mock response
agent-browser network unroute [url]            # Remove routes
agent-browser network requests                 # View tracked requests
agent-browser network requests --filter api    # Filter requests
```

### Tabs & Windows
```bash
agent-browser tab                 # List tabs
agent-browser tab new [url]       # New tab
agent-browser tab 2               # Switch to tab
agent-browser tab close           # Close tab
agent-browser window new          # New window
```

### Frames
```bash
agent-browser frame "#iframe"     # Switch to iframe
agent-browser frame main          # Back to main frame
```

### Dialogs
```bash
agent-browser dialog accept [text]  # Accept dialog
agent-browser dialog dismiss        # Dismiss dialog
```

### JavaScript
```bash
agent-browser eval "document.title"   # Run JavaScript
```

## Example: Form submission

```bash
agent-browser open https://example.com/form
agent-browser snapshot -i
# Output shows: textbox "Email" [ref=e1], textbox "Password" [ref=e2], button "Submit" [ref=e3]

agent-browser fill @e1 "user@example.com"
agent-browser fill @e2 "password123"
agent-browser click @e3
agent-browser wait --load networkidle
agent-browser snapshot -i  # Check result
```

## Example: Authentication with saved state

```bash
# Login once
agent-browser open https://app.example.com/login
agent-browser snapshot -i
agent-browser fill @e1 "username"
agent-browser fill @e2 "password"
agent-browser click @e3
agent-browser wait --url "**/dashboard"
agent-browser state save auth.json

# Later sessions: load saved state
agent-browser state load auth.json
agent-browser open https://app.example.com/dashboard
```

## Sessions (parallel browsers)

```bash
agent-browser --session test1 open site-a.com
agent-browser --session test2 open site-b.com
agent-browser session list
```

## JSON output (for parsing)

Add `--json` for machine-readable output:
```bash
agent-browser snapshot -i --json
agent-browser get text @e1 --json
```

## Debugging

```bash
agent-browser open example.com --headed              # Show browser window
agent-browser console                                # View console messages
agent-browser errors                                 # View page errors
agent-browser record start ./debug.webm   # Record from current page
agent-browser record stop                            # Save recording
agent-browser open example.com --headed  # Show browser window
agent-browser --cdp 9222 snapshot        # Connect via CDP
agent-browser console                    # View console messages
agent-browser console --clear            # Clear console
agent-browser errors                     # View page errors
agent-browser errors --clear             # Clear errors
agent-browser highlight @e1              # Highlight element
agent-browser trace start                # Start recording trace
agent-browser trace stop trace.zip       # Stop and save trace
```
"""
