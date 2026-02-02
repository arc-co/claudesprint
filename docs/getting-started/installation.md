# Installation

## Requirements

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.10+ | Runtime |
| Claude Code CLI | Latest | AI execution engine |

### Platform Support

- **macOS & Linux:** Fully supported
- **Windows:** Use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install)

## Install ClaudeSprint

### Using pip (Recommended)

```bash
pip install claudesprint
```

### Using pipx (Isolated Environment)

```bash
pipx install claudesprint
```

### From Source

```bash
git clone https://github.com/arc-co/claudesprint.git
cd claudesprint
pip install -e ".[dev]"
```

## Install Claude Code CLI

ClaudeSprint requires the Claude Code CLI to be installed and authenticated.

1. Install following the [official guide](https://docs.anthropic.com/en/docs/claude-code)

2. Authenticate:
   ```bash
   claude login
   ```

3. Verify:
   ```bash
   claude --version
   ```

## Verify Installation

Run the doctor command to check your environment:

```bash
claudesprint doctor
```

This checks:

- Python version
- Claude CLI installation
- Claude CLI authentication
- Optional dependencies

Use `--fix` to auto-install missing optional packages:

```bash
claudesprint doctor --fix
```

## Optional Dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| `agent-browser` | Browser automation for E2E testing | `npm install -g agent-browser` |
| `nicegui` | Real-time dashboard | Included by default |

### Browser Automation Setup

For projects with UI testing:

```bash
# Install agent-browser
npm install -g agent-browser

# Install browser dependencies
agent-browser install           # macOS
agent-browser install --with-deps  # Linux
```

## Next Steps

- [Quickstart Guide](quickstart.md) - Set up your first project
