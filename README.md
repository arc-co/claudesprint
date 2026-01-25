# ClaudeSprint v2

> [!CAUTION]
> **Alpha Software** - This project is in early development. APIs, configuration formats, and behavior may change without notice. Use in production environments at your own risk. Please report issues and feedback on [GitHub Issues](https://github.com/arc-co/claudesprint/issues).

A dual-loop agentic workflow for autonomous software development, aligned with Anthropic's ["Effective harnesses for long-running agents"](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) research.

ClaudeSprint orchestrates Claude Code sessions to build complete features autonomously - from specification to tested, committed code - while maintaining context across sessions through structured JSON artifacts.

## Why ClaudeSprint?

Traditional AI coding assistants lose context between sessions. ClaudeSprint solves this with:

- **Fresh sessions per step** - Each workflow step gets a clean context, preventing hallucination accumulation
- **Structured handoffs** - JSON artifacts (`sprint.json`, `current_issue.json`) pass verified state between sessions
- **Agent-driven decisions** - The AI selects issues based on dependencies, risk, and context continuity
- **Validation gates** - Schema validation, tests, and code review before any commit
- **Recovery built-in** - Automatic backup/restore handles crashes and failures

## Architecture

ClaudeSprint uses a two-loop architecture:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SPRINT LOOP (Outer)                               │
│                         Project Management Layer                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────┐    ┌──────────────┐    ┌───────────────┐    ┌────────────┐  │
│   │  Load    │───▶│ Get Bearings │───▶│ Select Issue  │───▶│   Enter    │  │
│   │ Sprint   │    │ & Prioritize │    │ (Agent-Driven)│    │ Issue Loop │  │
│   └──────────┘    └──────────────┘    └───────────────┘    └─────┬──────┘  │
│         ▲                                                        │         │
│         │                                                        │         │
│         │         ┌───────────────────────────────────┐          │         │
│         └─────────│ Mark Complete, Clear Issue State  │◀─────────┘         │
│                   └───────────────────────────────────┘                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           ISSUE LOOP (Inner)                                │
│                          Execution Layer                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   select-issue ──▶ read-docs ──▶ implement ──▶ write-tests ──▶ run-tests   │
│                                                                     │       │
│                                      ┌──────────────────────────────┘       │
│                                      ▼                                      │
│                               ┌─────────────┐                               │
│                               │ Tests Pass? │                               │
│                               └──────┬──────┘                               │
│                          yes ┌───────┴───────┐ no                           │
│                              ▼               ▼                               │
│                    browser-validation    fix-tests ──┐                      │
│                              │                       │                      │
│                              ▼                       └──▶ run-tests         │
│                         code-review                                         │
│                              │                                              │
│                    ┌────────┴────────┐                                      │
│               pass │                 │ issues                               │
│                    ▼                 ▼                                      │
│              update-docs    fix-code-review-issues ──▶ run-tests            │
│                    │                                                        │
│                    ▼                                                        │
│              stage-changes ──▶ commit-changes ──▶ complete-issue            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Sprint Loop (Outer)
Manages the overall sprint until all issues are complete:
1. Loads `sprint.json` - the source of truth for all issues
2. Runs "Get Bearings" - summarizes status, optionally re-prioritizes
3. Agent selects the next issue based on dependencies, impact, and context
4. Creates `current_issue.json` to track active work
5. Enters the Issue Loop
6. On completion: marks issue done, clears state, repeats

### Issue Loop (Inner)
Executes a single issue through a structured workflow:
- **read-docs**: Gather relevant documentation
- **implement**: Make minimal, focused code changes
- **write-tests**: Add tests for acceptance criteria
- **run-tests**: Execute the test suite
- **fix-tests**: Debug failures (distinguishes code bugs from test bugs)
- **browser-validation**: E2E validation for UI features
- **code-review**: Automated review against the spec
- **commit**: Stage and commit only after all gates pass

## Prerequisites

### Platform Support

- **macOS & Linux:** Fully supported.
- **Windows:** **NOT supported natively.** You must use [WSL2 (Windows Subsystem for Linux)](https://learn.microsoft.com/en-us/windows/wsl/install) to run this project.

### Required Dependencies

Install these **before** running `setup.sh`:

| Dependency | Version | Installation | Verify |
|------------|---------|--------------|--------|
| **Claude Code CLI** | Latest | [Installation Guide](https://docs.anthropic.com/en/docs/claude-code) | `claude --version` |
| **Python** | 3.10+ | [python.org](https://www.python.org/downloads/) | `python3 --version` |
| **Node.js** | 18+ | [nodejs.org](https://nodejs.org/) | `node --version` |
| **npm** | 8+ | Included with Node.js | `npm --version` |
| **Git** | Any | [git-scm.com](https://git-scm.com/) | `git --version` |

> **Critical:** Claude Code CLI must be installed and authenticated. Run `claude login` after installation.

### Python Dependencies (Auto-installed)

These are installed automatically by `setup.sh` via pip:

| Package | Version | Purpose |
|---------|---------|---------|
| `rich` | >=14.0.0 | Terminal formatting and output |
| `typer` | >=0.15.0 | CLI framework |
| `pydantic` | >=2.10.0 | Data validation and settings |
| `pydantic-settings` | >=2.0.0 | Configuration management |
| `httpx` | >=0.28.0 | HTTP client for notifications |

### Optional Dependencies

| Tool | Purpose | Installation |
|------|---------|--------------|
| `agent-browser` | Browser automation for E2E UI testing | `npm install -g agent-browser && agent-browser install` |
| `jq` | JSON parsing in shell (helpful for debugging) | `brew install jq` or `apt install jq` |
| Context7 MCP | Real-time library documentation lookup | [Context7 docs](https://github.com/upstash/context7) |

> **Note:** `agent-browser` is installed by default with `setup.sh`. Skip with `./setup.sh --no-browser`.

## Installation

### Step 1: Verify Prerequisites

Before proceeding, ensure all required dependencies are installed:

```bash
# Check each dependency
claude --version      # Claude Code CLI (required)
python3 --version     # Python 3.10+ (required)
node --version        # Node.js 18+ (required)
npm --version         # npm 8+ (required)
git --version         # Git (required)
```

If any command fails, install the missing dependency from the links in [Prerequisites](#prerequisites).

### Step 2: Clone and Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd <repo-name>

# Run the setup script
./setup.sh
```

The setup script will:
1. Create a Python virtual environment (`.venv/`)
2. Install the `claudesprint` CLI and all Python dependencies
3. Install `agent-browser` for browser automation (skip with `--no-browser`)
4. Verify the installation

### Step 3: Activate and Verify

```bash
# Activate the virtual environment
source .venv/bin/activate

# Verify ClaudeSprint is working
claudesprint status

# (Optional) Verify agent-browser
agent-browser --version
```

### Setup Options

```bash
./setup.sh              # Full setup (recommended)
./setup.sh --no-browser # Skip agent-browser installation
./setup.sh --no-venv    # Use system Python (not recommended)
./setup.sh --help       # Show all options
```

## Cost Awareness & Limits

ClaudeSprint runs autonomous loops that consume API tokens. By default, critical steps (Implementation, Code Review, Fix Tests) use **Claude Opus**, while others use Sonnet.

**To control costs:**

1. **Set Iteration Limits:** Always start with `claudesprint run -n 5` to verify behavior before running unlimited.
2. **Override Models:** Use `CLAUDESPRINT_MODEL_OVERRIDE=sonnet` to force cheaper models for all steps.
3. **Monitor Usage:** Check your Anthropic Console dashboard regularly.

## Quick Start

### 1. Initialize a Sprint

```bash
# Initialize from the example spec
claudesprint init --spec .claude/claudesprint/specs/examples/textbook-exchange-mvp.md

# View the generated sprint
claudesprint sprints
```

### 2. Run the Workflow

```bash
# Start the autonomous workflow
claudesprint run --sprint .claude/claudesprint/sprints/SPEC_01/sprint.json

# Or limit iterations
claudesprint run -n 10
```

## Demo: TextBook Exchange MVP

The repository includes a complete example specification for a textbook exchange marketplace:

**Tech Stack:**
- TypeScript + Express + Handlebars
- SQLite + Drizzle ORM
- HTMX for interactivity
- Session-based auth with OTP

**Features:**
- User authentication via email OTP
- Browse listings with pagination
- Create/edit/delete your own listings
- Seller contact information on detail pages

To build this demo:

```bash
# Setup the environment
./setup.sh
source .venv/bin/activate

# Initialize the sprint
claudesprint init --spec .claude/claudesprint/specs/examples/textbook-exchange-mvp.md

# Run ClaudeSprint - it will autonomously:
# 1. Set up the project structure
# 2. Create the database schema
# 3. Build the Express app with routes
# 4. Implement auth, listings, and UI
# 5. Test and commit each feature
claudesprint run
```

Watch as ClaudeSprint autonomously builds the complete application, issue by issue.

## CLI Reference

```bash
claudesprint status              # Check workflow state
claudesprint init --spec FILE    # Create sprint from specification
claudesprint run                 # Execute the workflow
claudesprint run -n 10           # Limit to 10 iterations
claudesprint sprints             # List available sprints
claudesprint reset               # Clear current issue state
claudesprint plan --spec FILE    # Update sprint from modified spec
claudesprint validate            # Validate JSON artifacts
claudesprint models              # Show model configuration
claudesprint notify TYPE MSG     # Send manual notification
```

## Project Structure

```
.claude/
├── CLAUDE.md                 # Project instructions for Claude
├── skills/                   # Skills (agent-browser, etc.)
└── claudesprint/             # ClaudeSprint system
    ├── config/               # Configuration
    │   ├── project.json      # Dev server, URLs
    │   ├── hooks.json        # Test/build commands
    │   ├── models.json       # Per-step model selection
    │   └── notifications.json
    ├── prompts/              # Workflow step prompts
    ├── schemas/              # JSON validation schemas
    ├── specs/                # Specification files
    │   └── examples/         # Example specs
    ├── sprints/              # Generated sprints
    │   └── SPEC_01/
    │       └── sprint.json
    ├── project/              # Runtime state
    │   ├── current_issue.json
    │   └── current_issue.log
    └── src/claudesprint/     # Python package
```

## Configuration

### Model Selection

ClaudeSprint optimizes costs by using different models for different steps:

| Step | Default Model | Rationale |
|------|---------------|-----------|
| `implement` | Opus | Core code generation |
| `fix-tests` | Opus | Nuanced judgment |
| `code-review` | Opus | Critical quality gate |
| `select-issue` | Sonnet | Algorithmic selection |
| `write-tests` | Sonnet | Pattern-based |
| Others | Sonnet | Lower-stakes steps |

Override via config or environment:
```bash
CLAUDESPRINT_MODEL_OVERRIDE=opus claudesprint run
```

### Hooks

Configure test commands in `.claude/claudesprint/config/hooks.json`:

```json
{
  "validate": {
    "command": "npm run validate",
    "timeout": 600
  },
  "test": {
    "command": "npm test",
    "timeout": 300
  }
}
```

### Notifications

Get notified of progress via Bark (iOS) in `.claude/claudesprint/config/notifications.json`:

```json
{
  "enabled": true,
  "bark": {
    "enabled": true,
    "url": "https://api.day.app/YOUR_KEY"
  }
}
```

## Writing Specifications

Specifications define what ClaudeSprint will build. Place them in `.claude/claudesprint/specs/`:

```markdown
# SPEC 01 - Feature Name

## Purpose
What this spec delivers.

## Constraints
- Technical constraints
- What NOT to do

## Deliverables
- Specific outcomes

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

The `claudesprint init` command parses specifications and generates structured sprints with individual issues, dependencies, and acceptance criteria.

## Troubleshooting

### "current_issue.json validation failed"
```bash
claudesprint validate  # See which fields are missing
claudesprint reset     # Start fresh
```

### Stuck in a loop
Check `current_issue.json` for `current_failures` - there may be unresolved issues blocking progress.

### Max retry limit reached
```bash
# Review failures
cat .claude/claudesprint/project/current_issue.json | jq '.current_failures'

# Override limit if needed
CLAUDESPRINT_MAX_RETRY=10 claudesprint run
```

### Browser validation failing
```bash
# Reinstall browser dependencies
agent-browser install --with-deps  # Linux
agent-browser install              # macOS
```

### "Command not found: claude"
The Claude Code CLI is missing from your PATH. Install it following the [official guide](https://docs.anthropic.com/en/docs/claude-code) and verify by running `claude --version`.

### "npm: command not found" or Agent-Browser errors
Ensure Node.js is installed. If using the default setup, `agent-browser` is installed via npm. Verify with `node --version` and `npm --version`.

## Data & Privacy

ClaudeSprint runs locally on your machine.

- Your code is sent to Anthropic's API via the Claude CLI for processing.
- No third-party servers (other than Anthropic) receive your code.
- State files (`current_issue.json`, `sprint.json`) are stored locally in `.claude/`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on:

- Contributing to the core engine (`.claude/claudesprint/`)
- Contributing example specifications
- Governance: treating claudesprint as vendored code vs. modifying it

**Quick start for contributors:**
1. Fork the repository
2. Create a feature branch
3. Make your changes and test them
4. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

Built on insights from Anthropic's research on effective agent harnesses and the Claude Code development experience.
