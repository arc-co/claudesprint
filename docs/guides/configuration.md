# Configuration

ClaudeSprint uses configuration files in `.claudesprint/config/`.

## Project Structure

```
.claudesprint/
├── config/
│   ├── project.json      # Project settings
│   ├── hooks.json        # Test/build commands
│   ├── models.json       # Per-step model selection
│   └── notifications.json # Alert settings
├── specs/                # Specification files
├── sprints/              # Generated sprints
├── project/              # Runtime state
└── state/                # Session state
```

## Project Configuration

`.claudesprint/config/project.json`:

```json
{
  "name": "my-project",
  "dev_server": {
    "url": "http://localhost:3000",
    "start_command": "npm run dev",
    "health_check": "/health"
  }
}
```

| Field | Purpose |
|-------|---------|
| `name` | Project identifier |
| `dev_server.url` | Base URL for browser testing |
| `dev_server.start_command` | Command to start dev server |
| `dev_server.health_check` | Endpoint to verify server is running |

## Hooks

`.claudesprint/config/hooks.json`:

```json
{
  "validate": {
    "command": "npm run lint && npm run typecheck",
    "timeout": 120
  },
  "test": {
    "command": "npm test",
    "timeout": 300
  },
  "build": {
    "command": "npm run build",
    "timeout": 180
  }
}
```

| Hook | When Used |
|------|-----------|
| `validate` | Before committing changes |
| `test` | During run-tests step |
| `build` | After implementation |

## Model Selection

`.claudesprint/config/models.json`:

```json
{
  "default": "sonnet",
  "steps": {
    "implement": "opus",
    "fix-tests": "opus",
    "code-review": "opus"
  }
}
```

### Default Model Assignments

| Step | Default | Rationale |
|------|---------|-----------|
| `implement` | Opus | Core code generation |
| `fix-tests` | Opus | Nuanced debugging |
| `code-review` | Opus | Quality judgment |
| `select-issue` | Sonnet | Algorithmic selection |
| `write-tests` | Sonnet | Pattern-based |
| `read-docs` | Sonnet | Information gathering |
| `commit-changes` | Sonnet | Structured task |

### Override All Models

Use environment variable:

```bash
# Use Sonnet for everything (cheaper)
CLAUDESPRINT_MODEL_OVERRIDE=sonnet claudesprint run

# Use Opus for everything (higher quality)
CLAUDESPRINT_MODEL_OVERRIDE=opus claudesprint run
```

## Notifications

`.claudesprint/config/notifications.json`:

```json
{
  "enabled": true,
  "bark": {
    "enabled": true,
    "url": "https://api.day.app/YOUR_KEY"
  }
}
```

### Bark (iOS)

[Bark](https://github.com/Finb/Bark) sends push notifications to iOS:

1. Install Bark app from App Store
2. Get your notification URL
3. Add to config

Notifications are sent on:
- Sprint started/completed
- Issue completed
- Errors requiring attention

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `CLAUDESPRINT_MODEL_OVERRIDE` | Force specific model | `sonnet` |
| `CLAUDESPRINT_MAX_RETRY` | Max retries per issue | `10` |
| `CLAUDESPRINT_LOG_LEVEL` | Logging verbosity | `DEBUG` |

## Claude Code Integration

ClaudeSprint installs hooks in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": ".*",
        "hooks": ["claudesprint hook --type server-guard"]
      }
    ],
    "Stop": [
      {
        "matcher": ".*",
        "hooks": ["claudesprint hook --type autonomous-continue"]
      }
    ]
  }
}
```

These hooks:
- **server-guard** - Prevents hanging on interactive commands
- **autonomous-continue** - Enables workflow continuation

Hooks only activate when a ClaudeSprint session is running (detected via lock file).
