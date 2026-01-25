# Documentation Navigation

Use this file to configure documentation sidebar navigation.

## Sidebar Structure

```yaml
- Getting Started
  - Introduction & Philosophy: getting-started/introduction.md
  - Installation (Drop-in): getting-started/installation.md
  - Quickstart: getting-started/quickstart.md

- Core Concepts
  - Architecture: concepts/architecture.md
  - State & Artifacts: concepts/state-management.md
  - Workflow Steps: concepts/workflow-steps.md

- Guides
  - Specs & Scoping (Best Practices): guides/specifications-and-scoping.md
  - Configuration: guides/configuration.md
  - Browser Automation: guides/browser-automation.md
  - Cost Management: guides/cost-management.md
  - Advanced Workflows (Parallel Runs): guides/advanced-workflows.md

- Reference
  - CLI Commands: reference/cli-commands.md
  - JSON Schemas: reference/schema-reference.md
  - Troubleshooting: reference/troubleshooting.md

- Development
  - Contributing: development/contributing.md
  - Customizing Prompts: development/prompt-engineering.md
  - Engine Internals: development/engine-internals.md
```

## File Inventory

### Getting Started (3 files)
| File | Description |
|------|-------------|
| `getting-started/introduction.md` | Philosophy, dual-loop, template model |
| `getting-started/installation.md` | Setup for new and existing projects |
| `getting-started/quickstart.md` | End-to-end demo walkthrough |

### Core Concepts (3 files)
| File | Description |
|------|-------------|
| `concepts/architecture.md` | Dual-loop architecture, state flow |
| `concepts/state-management.md` | JSON artifacts, validation |
| `concepts/workflow-steps.md` | All 13 steps detailed |

### Guides (5 files)
| File | Description |
|------|-------------|
| `guides/specifications-and-scoping.md` | **Critical**: How to write specs |
| `guides/configuration.md` | hooks.json, project.json, models.json |
| `guides/browser-automation.md` | agent-browser usage |
| `guides/cost-management.md` | Model selection, optimization |
| `guides/advanced-workflows.md` | Parallel, CI/CD, teams |

### Reference (3 files)
| File | Description |
|------|-------------|
| `reference/cli-commands.md` | All CLI commands |
| `reference/schema-reference.md` | sprint.json, current_issue.json schemas |
| `reference/troubleshooting.md` | Common issues and solutions |

### Development (3 files)
| File | Description |
|------|-------------|
| `development/contributing.md` | How to contribute |
| `development/prompt-engineering.md` | Customizing prompts |
| `development/engine-internals.md` | Python codebase overview |

### Root (2 files)
| File | Description |
|------|-------------|
| `index.md` | Documentation home page |
| `NAVIGATION.md` | This file |

## Total: 19 documentation files

## Cross-Reference Links

Key pages that should be linked from multiple places:

1. **Installation** → linked from Introduction, Quickstart
2. **Specifications & Scoping** → linked from Quickstart, Configuration, Troubleshooting
3. **Configuration** → linked from Installation, all Guides
4. **Troubleshooting** → linked from CLI Commands, all workflow concept pages
5. **Architecture** → linked from State Management, Workflow Steps

## Documentation Style Guide

### Headers
- H1 (#) for page title only
- H2 (##) for major sections
- H3 (###) for subsections
- H4 (####) sparingly for sub-subsections

### Code Blocks
- Use language hints: ```bash, ```json, ```python, ```markdown
- Keep examples short and focused
- Include comments for complex examples

### Tables
- Use for reference data (commands, options, values)
- Keep columns concise
- Align consistently

### Links
- Use relative paths for internal links
- Link to specific sections with anchors
- Avoid broken links (validate regularly)

### Tone
- Direct and imperative for instructions
- Technical but accessible
- Avoid marketing language
- Focus on "what" and "how", less on "why" (except in Introduction)
