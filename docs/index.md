# ClaudeSprint Documentation

**ClaudeSprint** is an autonomous software development orchestrator that transforms Claude Code into a disciplined, self-managing development agent. It implements a structured workflow that takes a project specification and systematically delivers working, tested code.

## Quick Links

- **New to ClaudeSprint?** Start with the [Introduction](./getting-started/introduction.md)
- **Setting up?** Follow the [Installation Guide](./getting-started/installation.md)
- **Ready to try it?** Run through the [Quickstart](./getting-started/quickstart.md)

## Documentation Sections

### Getting Started

Get up and running with ClaudeSprint.

- [Introduction & Philosophy](./getting-started/introduction.md) - What ClaudeSprint is and why it exists
- [Installation](./getting-started/installation.md) - Setup for new and existing projects
- [Quickstart](./getting-started/quickstart.md) - Your first sprint in minutes

### Core Concepts

Understand how ClaudeSprint works under the hood.

- [Architecture](./concepts/architecture.md) - The dual-loop system explained
- [State Management](./concepts/state-management.md) - How context persists between sessions
- [Workflow Steps](./concepts/workflow-steps.md) - The 13 steps of the Issue Loop

### Guides

Best practices and how-to guides for effective use.

- [Specifications & Scoping](./guides/specifications-and-scoping.md) - **Critical**: Write specs that work
- [Configuration](./guides/configuration.md) - Customize hooks, models, and settings
- [Browser Automation](./guides/browser-automation.md) - E2E testing with agent-browser
- [Cost Management](./guides/cost-management.md) - Optimize model usage and spending
- [Advanced Workflows](./guides/advanced-workflows.md) - Parallel execution, CI/CD, teams

### Reference

Technical specifications and command reference.

- [CLI Commands](./reference/cli-commands.md) - Complete command documentation
- [Schema Reference](./reference/schema-reference.md) - JSON schema specifications
- [Troubleshooting](./reference/troubleshooting.md) - Common issues and solutions

### Development

For contributors and those customizing the engine.

- [Contributing](./development/contributing.md) - How to contribute improvements
- [Prompt Engineering](./development/prompt-engineering.md) - Customize agent behavior
- [Engine Internals](./development/engine-internals.md) - How the engine works

## Key Concepts

### Dual-Loop Architecture

ClaudeSprint runs two nested loops:

1. **Sprint Loop** (Outer): Manages the project, selects issues, tracks progress
2. **Issue Loop** (Inner): Executes one issue through implementation, testing, and commit

### Template Model

ClaudeSprint is a **template**, not a package. You own the code in `.claude/claudesprint/`, allowing deep customization without fighting upstream abstractions.

### Specification-Driven

Everything starts with a specification. Clear, testable acceptance criteria drive the entire workflow. The agent implements exactly what you specify—no more, no less.

### Quality Gates

The workflow enforces gates that prevent progress without passing:
- Tests must pass before code review
- Code review must pass before commit
- Commits only happen with clean validation

## Quick Start

```bash
# 1. Setup
./setup.sh
source .venv/bin/activate

# 2. Create a spec
cat > .claude/claudesprint/specs/SPEC_01.md << 'EOF'
# My Feature

## Feature 1: Hello World
- Display "Hello World" on the homepage
EOF

# 3. Initialize and run
claudesprint init --spec SPEC_01.md
claudesprint run
```

## Getting Help

- **Issues**: Check [Troubleshooting](./reference/troubleshooting.md) first
- **Bugs**: Open an issue with reproduction steps
- **Questions**: Start a discussion

---

*ClaudeSprint implements Anthropic's "Effective harnesses for long-running agents" research, applying Extreme Programming principles to autonomous development.*
