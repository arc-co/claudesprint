# ClaudeSprint v2

Autonomous workflow orchestration for AI-driven development.

## Directory Structure

```
claudesprint/
├── src/claudesprint/        # Python package
│   ├── cli.py        # CLI commands (Typer)
│   ├── core/         # Workflow engine
│   ├── models/       # Pydantic data models
│   ├── services/     # Git, notification, file services
│   ├── utils/        # Utilities
│   └── validation/   # Validators
├── prompts/          # PROMPT_*.md workflow prompts
├── schemas/          # JSON schemas for validation
├── scripts/          # Entry point scripts
├── tests/            # Test suite
├── pyproject.toml    # Package configuration
└── README.md         # This file
```

## Installation

**Recommended:** Use the root-level setup script:
```bash
# From project root
./setup.sh                # Creates venv and installs claudesprint
source .venv/bin/activate # Activate the environment
```

**Manual installation:**
```bash
cd .claude/claudesprint
pip install -e ".[dev]"
```

**Note:** The setup script also installs `agent-browser` for e2e browser testing by default.
To skip browser automation: `./setup.sh --no-browser`

## Usage

```bash
claudesprint             # Run workflow (default)
claudesprint run -n 10    # Max 10 iterations
claudesprint init         # Initialize project
claudesprint plan         # Run planning mode
claudesprint status       # Show current status
claudesprint reset        # Reset to initial state
claudesprint step <name>  # Run specific step
claudesprint validate     # Validate current_issue.json
claudesprint notify <type> <msg>  # Send notification
```

## Examples

### Initialize a Sprint from a Specific Spec

```bash
# Initialize from a spec file (creates .claude/claudesprint/sprints/SPEC_01/sprint.json)
claudesprint init --spec .claude/claudesprint/specs/SPEC_01.md

# Initialize from spec in different location
claudesprint init --spec docs/specs/MY_FEATURE.md

# Short form
claudesprint init -s .claude/claudesprint/specs/SPEC_01.md
```

### Run a Sprint from a Specific sprint.json

```bash
# Run workflow targeting a specific sprint
claudesprint run --sprint .claude/claudesprint/sprints/SPEC_01/sprint.json

# Run with iteration limit
claudesprint run --sprint .claude/claudesprint/sprints/SPEC_01/sprint.json -n 10

# Short form
claudesprint run -S .claude/claudesprint/sprints/SPEC_01/sprint.json
```

### Full Workflow Example

```bash
# 1. Create a sprint from your spec
claudesprint init --spec .claude/claudesprint/specs/MVP.md

# 2. Check the generated sprint
cat .claude/claudesprint/sprints/MVP/sprint.json

# 3. Start executing the sprint
claudesprint run --sprint .claude/claudesprint/sprints/MVP/sprint.json

# 4. Check progress anytime
claudesprint status

# 5. Resume after interruption (continues from current_issue.json)
claudesprint run --sprint .claude/claudesprint/sprints/MVP/sprint.json
```

### Planning Mode (Update Existing Sprint)

```bash
# Re-analyze spec and update sprint with any gaps
claudesprint plan --spec .claude/claudesprint/specs/SPEC_01.md

# This updates .claude/claudesprint/sprints/SPEC_01/sprint.json with new issues if needed
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `claudesprint` | Run workflow |
| `claudesprint run` | Run workflow (supports flags) |
| `claudesprint run --sprint <path>` | Run workflow for specific sprint.json |
| `claudesprint init --spec <path>` | Initialize sprint from specific spec file |
| `claudesprint plan --spec <path>` | Update sprint from spec (gap analysis) |
| `claudesprint status` | Show current status |
| `claudesprint reset` | Reset current issue |
| `claudesprint step <name>` | Run specific step |
| `claudesprint validate` | Validate current_issue.json |
| `claudesprint notify <type> <msg>` | Send notification |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDESPRINT_MAX_RETRY` | 5 | Max retries before failing |
| `CLAUDESPRINT_CLAUDE_TIMEOUT` | 1800 | Claude session timeout (30 min) |
| `CLAUDESPRINT_TOTAL_TIMEOUT` | 28800 | Total runtime limit (8 hours) |

## Development

```bash
cd .claude/claudesprint

# Run tests
pytest

# Type checking
mypy src/claudesprint/

# Linting
ruff check src/claudesprint/
```

## Project-Specific Files

These files live at the `.claude/` level, not in `claudesprint/`:

- `.claude/claudesprint/project/current_issue.json` - Session state for current issue
- `.claude/claudesprint/project/current_issue.log` - Append-only progress log
- `.claude/claudesprint/sprints/<spec_id>/sprint.json` - Sprint definition with all issues
- `.claude/claudesprint/config/notifications.json` - Notification settings
- `.claude/claudesprint/specs/` - Project specifications
