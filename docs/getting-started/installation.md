# Installation

ClaudeSprint is a Python CLI tool that can be installed globally and used across multiple projects.

## Prerequisites

### Required

| Dependency | Version | Installation | Verify |
|------------|---------|--------------|--------|
| **Python** | 3.10+ | [python.org](https://www.python.org/downloads/) | `python3 --version` |
| **Claude Code CLI** | Latest | [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code) | `claude --version` |

### Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| macOS | Fully Supported | Native development |
| Linux | Fully Supported | Recommended for CI/production |
| Windows (WSL2) | Supported | Use Ubuntu WSL2; native Windows not tested |

### Optional

| Tool | Purpose | Installation |
|------|---------|--------------|
| **Git** | Version control features | `brew install git` or `apt install git` |
| **Node.js 18+** | For agent-browser and npm-based projects | [nodejs.org](https://nodejs.org/) |
| **agent-browser** | Browser automation for E2E testing | `npm install -g agent-browser` |

## Installation Methods

### Using pip (Recommended)

```bash
# Install from PyPI
pip install claudesprint

# Verify installation
claudesprint --version
```

### Using pipx (Isolated Environment)

[pipx](https://pypa.github.io/pipx/) installs Python CLI tools in isolated environments:

```bash
# Install pipx if needed
pip install pipx
pipx ensurepath

# Install ClaudeSprint
pipx install claudesprint

# Verify installation
claudesprint --version
```

### From Source

```bash
# Clone the repository
git clone https://github.com/arc-co/claudesprint.git
cd claudesprint

# Install in development mode
pip install -e ".[dev]"

# Verify installation
claudesprint --version
```

## Verify Installation

After installation, run the doctor command to verify all dependencies:

```bash
claudesprint doctor
```

Expected output:

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

Use `--verbose` for detailed information:

```bash
claudesprint doctor --verbose
```

Use `--fix` to attempt auto-installation of missing packages:

```bash
claudesprint doctor --fix
```

## Initialize a Project

To use ClaudeSprint in a project, initialize it:

```bash
cd your-project
claudesprint initrepo
```

This creates:
- `.claudesprint/state/` - Session state files
- `.claudesprint/prompts/` - Custom prompt overrides (optional)
- Injects ClaudeSprint hooks into `.claude/settings.json`

### Directory Structure After Initialization

```
your-project/
├── .claude/
│   └── settings.json    # Claude Code hooks (auto-configured)
├── .claudesprint/
│   ├── state/           # Runtime state files
│   └── prompts/         # Custom prompt overrides
├── src/                 # Your project code
└── ...
```

## Installing agent-browser

For browser-based E2E testing, install `agent-browser`:

```bash
# Install globally via npm
npm install -g agent-browser

# Install Playwright browsers
agent-browser install

# On Linux, include system dependencies
agent-browser install --with-deps
```

Verify installation:

```bash
agent-browser --version
```

If `agent-browser` is not installed, the `browser-validation` step will be skipped automatically.

## Troubleshooting

### "claudesprint: command not found"

The CLI is not in your PATH. Try:

```bash
# Check if installed
pip show claudesprint

# If using pipx
pipx ensurepath
source ~/.bashrc  # or ~/.zshrc
```

### Python version issues

ClaudeSprint requires Python 3.10+:

```bash
python3 --version
```

If you have multiple versions, use a specific one:

```bash
python3.11 -m pip install claudesprint
```

### Permission errors on Linux

If you get permission errors with global pip installs:

```bash
# Use pipx instead (recommended)
pip install pipx
pipx install claudesprint

# Or use user install
pip install --user claudesprint
```

### WSL2-specific issues

Ensure you're running WSL2, not WSL1:

```bash
wsl --list --verbose
```

If you see "1" under VERSION, upgrade:

```powershell
wsl --set-version Ubuntu 2
```

## Next Steps

- [Quickstart](./quickstart.md): Run through a demo to see ClaudeSprint in action
- [Configuration](../guides/configuration.md): Customize ClaudeSprint for your project
- [Prompt Customization](../guides/prompt-customization.md): Customize agent prompts
