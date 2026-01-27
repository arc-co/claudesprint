# Configuration

ClaudeSprint is highly configurable to match your project's stack, testing requirements, and workflow preferences. All configuration lives in `.claude/claudesprint/config/`.

## Configuration Files

| File | Purpose |
|------|---------|
| `hooks.json` | Test/build commands and timeouts |
| `project.json` | Dev server and project settings |
| `models.json` | Per-step model selection |
| `notifications.json` | Notification settings |

## Hooks Configuration

The `hooks.json` file defines commands for testing, linting, and building. The `run-tests` step uses these to validate your implementation.

### Location

`.claude/claudesprint/config/hooks.json`

### Basic Configuration

```json
{
  "validate": {
    "command": "npm run validate",
    "timeout": 600
  },
  "test": {
    "command": "npm test",
    "timeout": 300
  },
  "lint": {
    "command": "npm run lint",
    "timeout": 120
  },
  "typecheck": {
    "command": "npm run typecheck",
    "timeout": 120
  }
}
```

### Full Hook Options

```json
{
  "validate": {
    "command": "npm run validate",
    "timeout": 600,
    "working_dir": null,
    "env": {},
    "success_exit_codes": [0],
    "failure_patterns": ["FAIL", "error", "Error:"],
    "success_patterns": []
  }
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `command` | string | (required) | Shell command to run |
| `timeout` | number | 300 | Max seconds before timeout |
| `working_dir` | string\|null | null | Working directory (null = project root) |
| `env` | object | {} | Environment variables to set |
| `success_exit_codes` | number[] | [0] | Exit codes that indicate success |
| `failure_patterns` | string[] | [] | Output patterns that indicate failure |
| `success_patterns` | string[] | [] | Output patterns that indicate success |

### Stack-Specific Examples

#### TypeScript + Jest
```json
{
  "validate": {
    "command": "npm run validate",
    "timeout": 600,
    "failure_patterns": ["FAIL", "error TS"]
  },
  "test": {
    "command": "npm test -- --coverage",
    "timeout": 300
  },
  "typecheck": {
    "command": "npx tsc --noEmit",
    "timeout": 120
  }
}
```

#### Python + pytest
```json
{
  "validate": {
    "command": "make validate",
    "timeout": 600
  },
  "test": {
    "command": "pytest -v",
    "timeout": 300
  },
  "lint": {
    "command": "ruff check .",
    "timeout": 60
  },
  "typecheck": {
    "command": "mypy src/",
    "timeout": 120
  }
}
```

#### Go
```json
{
  "validate": {
    "command": "make test && make lint",
    "timeout": 300
  },
  "test": {
    "command": "go test ./...",
    "timeout": 300
  },
  "lint": {
    "command": "golangci-lint run",
    "timeout": 120
  }
}
```

#### Rust
```json
{
  "validate": {
    "command": "cargo test && cargo clippy",
    "timeout": 600
  },
  "test": {
    "command": "cargo test",
    "timeout": 300
  },
  "lint": {
    "command": "cargo clippy -- -D warnings",
    "timeout": 120
  }
}
```

## Project Configuration

The `project.json` file contains project-specific settings, primarily for browser validation.

### Location

`.claude/claudesprint/config/project.json`

### Configuration

```json
{
  "dev_server": {
    "url": "http://localhost:3000",
    "start_command": "npm run dev",
    "wait_seconds": 5
  }
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `dev_server.url` | string | "http://localhost:3000" | Base URL for browser validation |
| `dev_server.start_command` | string | "npm run dev" | Command to start the dev server |
| `dev_server.wait_seconds` | number | 5 | Seconds to wait after starting |

### Stack-Specific Examples

#### Next.js
```json
{
  "dev_server": {
    "url": "http://localhost:3000",
    "start_command": "npm run dev",
    "wait_seconds": 5
  }
}
```

#### Vite
```json
{
  "dev_server": {
    "url": "http://localhost:5173",
    "start_command": "npm run dev",
    "wait_seconds": 3
  }
}
```

#### Django
```json
{
  "dev_server": {
    "url": "http://localhost:8000",
    "start_command": "python manage.py runserver",
    "wait_seconds": 5
  }
}
```

#### Flask
```json
{
  "dev_server": {
    "url": "http://localhost:5000",
    "start_command": "flask run",
    "wait_seconds": 3
  }
}
```

## Model Configuration

The `models.json` file controls which Claude model is used for each workflow step.

### Location

`.claude/claudesprint/config/models.json`

### Configuration

```json
{
  "default_model": "opus",
  "model_override": null,
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
  },
  "special_step_models": {
    "init": "opus",
    "plan": "sonnet"
  }
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `default_model` | string | "opus" | Fallback model for unspecified steps |
| `model_override` | string\|null | null | Force all steps to use this model |
| `step_models` | object | (see above) | Model for each workflow step |
| `special_step_models` | object | (see above) | Model for init/plan commands |

### Model Selection Rationale

| Model | Best For | Steps |
|-------|----------|-------|
| **opus** | Complex judgment, code generation | implement, fix-tests, code-review, init |
| **sonnet** | Pattern-following, research | select-issue, read-docs, write-tests, update-docs |

### Override All Steps

To force a specific model for all steps:

**Via config:**
```json
{
  "model_override": "opus"
}
```

**Via environment:**
```bash
CLAUDESPRINT_MODEL_OVERRIDE=opus claudesprint run
```

### View Configuration

```bash
claudesprint models
```

## Notifications Configuration

The `notifications.json` file configures alerts for workflow events.

### Location

`.claude/claudesprint/config/notifications.json`

### Configuration

```json
{
  "enabled": true,
  "bark": {
    "enabled": true,
    "url": "https://api.day.app/YOUR_BARK_KEY"
  }
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Master enable/disable |
| `bark.enabled` | boolean | true | Enable Bark notifications |
| `bark.url` | string | (required if enabled) | Bark API URL with key |

### Disable Notifications

```json
{
  "enabled": false
}
```

### Notification Events

| Event | Trigger |
|-------|---------|
| `step` | Step completed successfully |
| `failure` | Max retry limit reached |
| `rate_limit` | Claude rate limit detected |
| `exit` | Workflow completed or stopped |

### Manual Notifications

```bash
claudesprint notify step "Custom message"
claudesprint notify failure "Something failed"
claudesprint notify exit "Workflow complete"
```

## Environment Variables

Configuration can also be set via environment variables:

| Variable | Purpose |
|----------|---------|
| `CLAUDESPRINT_MODEL_OVERRIDE` | Force model for all steps |
| `CLAUDESPRINT_MAX_RETRY` | Maximum retry count (default: 3) |
| `CLAUDESPRINT_LOG_LEVEL` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |

### Example Usage

```bash
# Force Opus for everything
CLAUDESPRINT_MODEL_OVERRIDE=opus claudesprint run

# Increase retry limit
CLAUDESPRINT_MAX_RETRY=5 claudesprint run

# Verbose logging
CLAUDESPRINT_LOG_LEVEL=DEBUG claudesprint run
```

## Validating Configuration

After modifying configuration files, validate them:

```bash
claudesprint validate
```

This checks:
- JSON syntax is valid
- Required fields are present
- Values are of correct type
- Referenced files/commands exist

## Configuration Best Practices

### 1. Match Your CI/CD

Use the same commands in `hooks.json` that your CI pipeline uses:

```json
{
  "validate": {
    "command": "make ci-validate"
  }
}
```

### 2. Set Appropriate Timeouts

Large test suites need longer timeouts:

```json
{
  "test": {
    "command": "npm test",
    "timeout": 900  // 15 minutes for large suites
  }
}
```

### 3. Use Failure Patterns

Catch failures that don't return non-zero exit codes:

```json
{
  "test": {
    "command": "npm test",
    "failure_patterns": ["FAIL", "Error:", "✗"]
  }
}
```

### 4. Optimize Model Selection

Use Sonnet for faster, cheaper operations that are validated by later steps:

```json
{
  "step_models": {
    "read-docs": "sonnet",      // Validated by implement step
    "write-tests": "sonnet",     // Validated by run-tests step
    "update-docs": "sonnet"      // Lower stakes
  }
}
```

## Next Steps

- [Specifications and Scoping](./specifications-and-scoping.md): Write effective specs
- [Browser Automation](./browser-automation.md): Configure e2e testing
- [Cost Management](./cost-management.md): Optimize model usage
