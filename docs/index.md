# ClaudeSprint

**Autonomous AI-driven software development.**

ClaudeSprint orchestrates [Claude Code](https://docs.anthropic.com/en/docs/claude-code) sessions to build complete features end-to-end—from specification to tested, committed code.

## The Problem

AI coding assistants lose context between sessions. Long conversations accumulate hallucinations. Manual handoffs break continuity.

## The Solution

ClaudeSprint implements a **dual-loop architecture** inspired by Anthropic's research on [effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents):

- **Fresh sessions per step** - Each workflow step gets clean context
- **Structured handoffs** - JSON artifacts pass verified state between sessions
- **Validation gates** - Tests and code review before any commit
- **Recovery built-in** - Automatic backup/restore handles failures

## Quick Start

```bash
# Install
pip install claudesprint

# Verify environment
claudesprint doctor

# Try the demo
claudesprint demo
```

The demo builds a complete URL shortener application autonomously—watch as ClaudeSprint implements features, writes tests, and commits code.

## Next Steps

- [Installation](getting-started/installation.md) - Detailed setup instructions
- [Quickstart Guide](getting-started/quickstart.md) - Set up your first project
- [Architecture](concepts/architecture.md) - Understand the dual-loop design
- [CLI Reference](reference/cli-commands.md) - All available commands
