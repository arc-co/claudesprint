# ClaudeSprint

**Autonomous AI-driven software development.** ClaudeSprint orchestrates Claude Code to build complete features end-to-end—from spec to tested, committed code.

[![PyPI](https://img.shields.io/pypi/v/claudesprint.svg)](https://pypi.org/project/claudesprint/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**[PyPI](https://pypi.org/project/claudesprint/)** | **[Documentation](https://claudesprint.com/docs)** | **[GitHub](https://github.com/arc-co/claudesprint)**

> **Alpha Software** - APIs and behavior may change. [Report issues](https://github.com/arc-co/claudesprint/issues)

## Why ClaudeSprint?

AI coding assistants lose context between sessions. ClaudeSprint solves this with:

- **Fresh sessions per step** - Clean context prevents hallucination accumulation
- **Structured handoffs** - JSON artifacts pass verified state between sessions
- **Validation gates** - Tests and code review before any commit
- **Recovery built-in** - Automatic backup/restore handles failures

## Quick Start

### 1. Install

```bash
pip install claudesprint
```

**Requirements:** Python 3.10+ and [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (authenticated)

### 2. Verify Setup

```bash
claudesprint doctor
```

### 3. Try the Demo

```bash
claudesprint demo
```

Watch ClaudeSprint build a complete URL shortener app autonomously.

### 4. Start Your Own Project

```bash
claudesprint quickstart
```

## How It Works

ClaudeSprint uses a dual-loop architecture:

```
SPRINT LOOP (outer)          ISSUE LOOP (inner)
├─ Load sprint.json          ├─ read-docs
├─ Select next issue    ──►  ├─ implement
├─ Enter issue loop          ├─ write-tests
├─ Mark complete             ├─ run-tests / fix-tests
└─ Repeat                    ├─ code-review
                             ├─ commit-changes
                             └─ complete
```

Each step runs in a fresh Claude session with focused context. State is passed via JSON artifacts, not conversation history.

[Learn more about the architecture →](https://claudesprint.com/docs/concepts/architecture)

## Commands

```bash
claudesprint quickstart      # Interactive project setup
claudesprint demo            # Try with sample project
claudesprint doctor          # Check environment
claudesprint run             # Execute workflow
claudesprint run -n 5        # Limit iterations
claudesprint status          # View current state
claudesprint reset           # Clear issue state
```

[Full CLI reference →](https://claudesprint.com/docs/reference/cli-commands)

## Cost Awareness

ClaudeSprint runs autonomous loops that consume API tokens. Control costs with:

```bash
# Limit iterations (recommended for testing)
claudesprint run -n 5

# Use cheaper models for all steps
CLAUDESPRINT_MODEL_OVERRIDE=sonnet claudesprint run
```

[Cost management guide →](https://claudesprint.com/docs/guides/cost-management)

## Documentation

- [Installation](https://claudesprint.com/docs/getting-started/installation)
- [Quickstart Guide](https://claudesprint.com/docs/getting-started/quickstart)
- [Writing Specifications](https://claudesprint.com/docs/guides/specifications)
- [Configuration](https://claudesprint.com/docs/guides/configuration)
- [Troubleshooting](https://claudesprint.com/docs/reference/troubleshooting)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT - see [LICENSE](LICENSE)
