# Installation

ClaudeSprint can be installed as a new project or dropped into an existing codebase. Both approaches are straightforward.

## Prerequisites

### Required

- **Python 3.10+**: The workflow engine is Python
- **Node.js 18+**: For running tests and the typical JavaScript/TypeScript stack
- **Claude Code CLI**: The underlying AI agent (install from Anthropic)

### Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| macOS | Fully Supported | Native development |
| Linux | Fully Supported | Recommended for CI/production |
| Windows (WSL2) | Supported | Use Ubuntu WSL2; native Windows not tested |

### Optional

- **Git**: For version control features (staging, commits, branches). The workflow functions without Git but skips commit-related steps.
- **agent-browser**: For browser-based e2e validation. Installed by default with `setup.sh`.

## New Project Setup

For a fresh project, run the setup script:

```bash
# Clone or create your project directory
mkdir my-project && cd my-project

# If starting from a template, clone it
git clone https://github.com/your-org/claudesprint-template.git .

# Run setup
./setup.sh

# Activate the virtual environment
source .venv/bin/activate

# Verify installation
claudesprint status
```

### What `setup.sh` Does

1. Creates a Python virtual environment (`.venv/`)
2. Installs the `claudesprint` package in editable mode
3. Installs `agent-browser` globally (for browser validation)
4. Validates the installation

### Setup Options

```bash
# Skip browser automation installation
./setup.sh --no-browser

# Use a specific Python version
PYTHON=python3.11 ./setup.sh

# Verbose output for debugging
./setup.sh --verbose
```

## Drop-in for Existing Projects

ClaudeSprint is designed to integrate into any existing codebase. Simply copy the infrastructure directory:

```bash
# From a project that has ClaudeSprint
cp -r /path/to/claudesprint-project/.claude/claudesprint .claude/

# Or clone just the claudesprint directory from a template
git clone --depth 1 https://github.com/your-org/claudesprint-template.git /tmp/cs
cp -r /tmp/cs/.claude/claudesprint .claude/
rm -rf /tmp/cs

# Run setup from your project root
cd your-project
./.claude/claudesprint/scripts/setup.sh

# Activate and verify
source .venv/bin/activate
claudesprint status
```

### Integration with Existing Projects

ClaudeSprint lives entirely within `.claude/claudesprint/`. It doesn't modify your:
- Package.json scripts (but does read them via `hooks.json`)
- Project structure
- Existing build/test configurations

You configure ClaudeSprint to use your existing commands by editing `.claude/claudesprint/config/hooks.json`:

```json
{
  "validate": {
    "command": "npm run validate",
    "timeout": 600
  },
  "test": {
    "command": "pytest",
    "timeout": 300
  },
  "lint": {
    "command": "make lint",
    "timeout": 120
  }
}
```

## Directory Structure After Installation

```
your-project/
├── .claude/
│   ├── claudesprint/          # ClaudeSprint infrastructure
│   │   ├── config/            # Configuration files
│   │   ├── docs/              # This documentation
│   │   ├── prompts/           # Workflow step prompts
│   │   ├── schemas/           # JSON schemas
│   │   ├── scripts/           # CLI and setup scripts
│   │   ├── specs/             # Your specification files go here
│   │   ├── sprints/           # Generated sprint files
│   │   ├── src/claudesprint/  # Python package
│   │   ├── tests/             # ClaudeSprint tests
│   │   └── pyproject.toml     # Package configuration
│   ├── skills/                # Skills (agent-browser, etc.)
│   ├── hooks/                 # Claude Code hooks
│   └── CLAUDE.md              # Project instructions for Claude
├── .venv/                     # Python virtual environment
├── src/                       # Your project source code
└── ...                        # Your other project files
```

## Verifying Installation

After installation, run these commands to verify everything is working:

```bash
# Check CLI is accessible
claudesprint --help

# Check current status
claudesprint status

# Validate schemas and state files
claudesprint validate

# List available sprints (will be empty for new projects)
claudesprint sprints

# Check model configuration
claudesprint models
```

Expected output from `claudesprint status` for a new project:

```
ClaudeSprint Status
==================
Current Issue: None
Sprint: None

Ready to initialize a sprint. Create a spec file in
.claude/claudesprint/specs/ and run:
  claudesprint init --spec YOUR_SPEC.md
```

## Installing agent-browser

The `browser-validation` step uses `agent-browser` for e2e testing. It's installed by default, but if you skipped it or need to reinstall:

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

If `agent-browser` is not installed, the `browser-validation` step will be skipped automatically with a warning. Unit tests still run via your configured test command.

## Troubleshooting Installation

### "claudesprint: command not found"

Ensure the virtual environment is activated:

```bash
source .venv/bin/activate
```

Or check that the package is installed:

```bash
pip list | grep claudesprint
```

### Python version issues

ClaudeSprint requires Python 3.10+. Check your version:

```bash
python3 --version
```

If you have multiple Python versions, specify the correct one:

```bash
PYTHON=python3.11 ./setup.sh
```

### Permission errors on Linux

If you get permission errors installing `agent-browser`, you may need to configure npm for global installs:

```bash
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### WSL2-specific issues

Ensure you're running in WSL2, not WSL1:

```bash
wsl --list --verbose
```

If you see "1" under VERSION, upgrade to WSL2:

```powershell
wsl --set-version Ubuntu 2
```

## Next Steps

- [Quickstart](./quickstart.md): Run through a demo to see ClaudeSprint in action
- [Configuration](../guides/configuration.md): Customize ClaudeSprint for your project
- [Specifications and Scoping](../guides/specifications-and-scoping.md): Learn how to write effective specs
