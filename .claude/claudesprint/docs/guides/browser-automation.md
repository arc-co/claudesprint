# Browser Automation

ClaudeSprint includes a `browser-validation` step that uses `agent-browser` for end-to-end testing. This validates UI acceptance criteria by actually interacting with your application in a real browser.

## Overview

The browser-validation step runs after tests pass and before code review. It:

1. Starts your dev server (if not running)
2. Opens a browser to your application
3. Interacts with UI elements
4. Verifies visual acceptance criteria
5. Captures screenshots as evidence
6. Reports any JavaScript errors

## When Browser Validation Runs

Browser validation runs for issues with UI-related categories:

| Category | Browser Validation |
|----------|-------------------|
| `ui` | Yes |
| `feature` | Yes (if has UI) |
| `api` | No (skipped) |
| `infrastructure` | No (skipped) |
| `testing` | No (skipped) |
| `docs` | No (skipped) |
| `bugfix` | Depends on what's being fixed |

## Prerequisites

### Installing agent-browser

```bash
# Install globally
npm install -g agent-browser

# Install browsers
agent-browser install

# On Linux, include system dependencies
agent-browser install --with-deps
```

### Configuring the Dev Server

Edit `.claude/claudesprint/config/project.json`:

```json
{
  "dev_server": {
    "url": "http://localhost:3000",
    "start_command": "npm run dev",
    "wait_seconds": 5
  }
}
```

## agent-browser Commands

### Navigation

```bash
# Open a URL
agent-browser open http://localhost:3000/login

# Navigate to a path (uses configured base URL)
agent-browser open /dashboard

# Wait for page load
agent-browser wait --load networkidle
```

### Page Inspection

```bash
# Get page snapshot (text content)
agent-browser snapshot

# Get interactive elements (buttons, inputs, links)
agent-browser snapshot -i

# Get both
agent-browser snapshot -a
```

### Interaction

```bash
# Click an element (using @ref from snapshot -i)
agent-browser click @e1

# Fill an input field
agent-browser fill @e2 "user@example.com"

# Type with key events
agent-browser type @e3 "password123"

# Press special keys
agent-browser press Enter
agent-browser press Tab
```

### Screenshots

```bash
# Full page screenshot
agent-browser screenshot evidence.png

# Element screenshot
agent-browser screenshot --element @e1 button.png
```

### Waiting

```bash
# Wait for network to be idle
agent-browser wait --load networkidle

# Wait for specific element
agent-browser wait --selector "#dashboard"

# Wait fixed time (seconds)
agent-browser wait 2
```

### Error Checking

```bash
# Get JavaScript console errors
agent-browser errors

# Clear error log
agent-browser errors --clear
```

### Cleanup

```bash
# Close browser
agent-browser close
```

## Example Validation Flow

Here's how the `browser-validation` step might validate a login feature:

```bash
# Start fresh
agent-browser open http://localhost:3000/login
agent-browser wait --load networkidle

# Take initial screenshot
agent-browser screenshot 01-login-page.png

# Get interactive elements
agent-browser snapshot -i
# Output:
# @e1: input[type="email"] placeholder="Email"
# @e2: input[type="password"] placeholder="Password"
# @e3: button "Sign In"

# Fill login form
agent-browser fill @e1 "test@example.com"
agent-browser fill @e2 "password123"
agent-browser screenshot 02-form-filled.png

# Submit
agent-browser click @e3
agent-browser wait --load networkidle

# Verify redirect to dashboard
agent-browser snapshot
# Verify "Dashboard" or expected content appears

agent-browser screenshot 03-dashboard.png

# Check for JavaScript errors
agent-browser errors
# Should be empty for success

# Cleanup
agent-browser close
```

## Acceptance Criteria Validation

Browser validation maps acceptance criteria to interactions:

### Criterion: "User can log in with valid credentials"
```bash
agent-browser open /login
agent-browser fill @email "valid@user.com"
agent-browser fill @password "correctpassword"
agent-browser click @submit
agent-browser wait --load networkidle
agent-browser snapshot
# Verify dashboard content visible
```

### Criterion: "Error message appears for invalid login"
```bash
agent-browser open /login
agent-browser fill @email "wrong@user.com"
agent-browser fill @password "wrongpassword"
agent-browser click @submit
agent-browser wait 2
agent-browser snapshot
# Verify "Invalid credentials" message visible
```

### Criterion: "Button is disabled during submission"
```bash
agent-browser fill @email "test@user.com"
agent-browser fill @password "password"
agent-browser click @submit
# Immediately check button state
agent-browser snapshot -i
# Verify button has disabled attribute
```

## Handling Dynamic Content

### Waiting for AJAX

```bash
# Wait for network to settle
agent-browser wait --load networkidle

# Or wait for specific element
agent-browser wait --selector ".data-loaded"
```

### Loading States

```bash
# Click and wait for loading to complete
agent-browser click @load-data
agent-browser wait --selector ".loading-spinner" --hidden
agent-browser wait --selector ".data-table"
```

### Animations

```bash
# Wait for animation to complete
agent-browser wait 1  # Simple delay
agent-browser wait --selector ".modal.visible"  # Wait for class
```

## Troubleshooting

### Browser doesn't start

```bash
# Verify installation
agent-browser --version

# Reinstall browsers
agent-browser install --force
```

### Dev server not running

The step will attempt to start it using `project.json` config. Verify:

```bash
# Test the start command manually
npm run dev
```

### Elements not found

```bash
# Get all interactive elements
agent-browser snapshot -i

# Check page content
agent-browser snapshot

# Screenshot to see what's visible
agent-browser screenshot debug.png
```

### Timeout errors

Increase wait times:

```bash
agent-browser wait --load networkidle --timeout 30000
```

### JavaScript errors

Check console for issues:

```bash
agent-browser errors
```

## Skipping Browser Validation

For issues that don't need browser testing, the step auto-skips based on category. You can also explicitly skip in the spec:

```markdown
### Feature: API Rate Limiting
**Category**: infrastructure
**Browser Validation**: Not required

[This will auto-skip browser-validation step]
```

## Screenshots as Evidence

Browser validation captures screenshots that serve as evidence of testing:

```
.claude/claudesprint/project/
├── screenshots/
│   ├── feature-001/
│   │   ├── 01-initial-page.png
│   │   ├── 02-form-filled.png
│   │   └── 03-success-state.png
│   └── feature-002/
│       └── ...
```

These can be reviewed to verify the agent tested the right things.

## Best Practices

### 1. Be Specific About URLs

```markdown
**Acceptance Criteria**:
- Login form accessible at `/login`
- Dashboard visible at `/dashboard` after login
```

### 2. Include Visual States

```markdown
**Acceptance Criteria**:
- Loading spinner visible during data fetch
- Empty state shown when no data
- Error banner shown on API failure
```

### 3. Test Error Cases

```markdown
**Acceptance Criteria**:
- 404 page shown for invalid URLs
- Session expired message after timeout
- Form validation errors displayed inline
```

### 4. Capture Key Transitions

```markdown
**Acceptance Criteria**:
- Button text changes from "Save" to "Saving..."
- Success toast appears after save
- Modal closes after confirmation
```

## Next Steps

- [Configuration](./configuration.md): Set up project.json for your stack
- [Workflow Steps](../concepts/workflow-steps.md): How browser-validation fits in
- [Specifications and Scoping](./specifications-and-scoping.md): Write testable UI criteria
