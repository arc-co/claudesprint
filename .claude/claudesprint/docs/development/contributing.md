# Contributing to ClaudeSprint

ClaudeSprint is designed as a template, meaning you own your copy. However, if you want to contribute improvements back to the core template, this guide explains how.

## Contribution Philosophy

### Template vs. Package Mindset

Unlike traditional packages, ClaudeSprint encourages forking and customization. There are two types of contributions:

1. **Core Contributions**: Improvements that benefit everyone
   - Bug fixes
   - Performance improvements
   - New workflow features
   - Better error handling

2. **Project-Specific Customizations**: Changes for your use case
   - Custom workflow steps
   - Team-specific prompts
   - Domain-specific validation
   - Keep these in your fork

### What Makes a Good Core Contribution

Ask yourself:
- Would 80% of users benefit from this?
- Does it follow the existing patterns?
- Is it backward compatible?
- Does it have tests?

## Development Setup

### Prerequisites

- Python 3.10+
- Node.js 18+ (for testing JavaScript projects)
- Git

### Setting Up Development Environment

```bash
# Clone the template repository
git clone https://github.com/your-org/claudesprint-template.git
cd claudesprint-template

# Create development virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".claude/claudesprint/[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests to verify setup
pytest .claude/claudesprint/tests/
```

### Project Structure

```
.claude/claudesprint/
├── src/claudesprint/          # Python package
│   ├── __init__.py
│   ├── cli.py                 # CLI entry point
│   ├── models.py              # Data models
│   ├── services/              # Business logic
│   │   ├── workflow.py        # Workflow engine
│   │   ├── state.py           # State management
│   │   ├── hooks.py           # Hook runner
│   │   └── notifications.py   # Notification service
│   └── utils/                 # Utilities
├── prompts/                   # Workflow step prompts
├── schemas/                   # JSON schemas
├── tests/                     # Test suite
├── config/                    # Default configuration
└── pyproject.toml            # Package configuration
```

## Making Changes

### Branch Naming

```
feature/add-parallel-execution
fix/retry-counter-reset
docs/update-installation-guide
refactor/simplify-state-management
```

### Commit Messages

Follow conventional commits:

```
feat(workflow): add parallel execution support

- Add worktree detection
- Support multiple current_issue.json files
- Update state management for isolation

Closes #123
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code refactoring
- `test`: Test additions/changes
- `chore`: Build, config changes

### Testing Your Changes

```bash
# Run all tests
pytest .claude/claudesprint/tests/

# Run specific test file
pytest .claude/claudesprint/tests/test_workflow.py

# Run with coverage
pytest --cov=claudesprint .claude/claudesprint/tests/

# Run type checking
mypy .claude/claudesprint/src/claudesprint/

# Run linting
ruff check .claude/claudesprint/src/
```

### Testing Workflow Changes

For changes to workflow behavior:

```bash
# Create a test project
mkdir /tmp/test-project
cd /tmp/test-project
git init

# Copy your modified claudesprint
cp -r /path/to/your/.claude .

# Create a simple spec
cat > .claude/claudesprint/specs/TEST_SPEC.md << 'EOF'
# Test Spec

## Feature 1: Hello World
- Print "Hello World"
EOF

# Run the workflow
source .venv/bin/activate
claudesprint init --spec TEST_SPEC.md
claudesprint run -n 5
```

## Contribution Areas

### Workflow Engine

Location: `src/claudesprint/services/workflow.py`

The workflow engine manages the dual-loop architecture. Contributions might include:
- New step types
- Better error recovery
- Parallel execution
- Performance optimization

### State Management

Location: `src/claudesprint/services/state.py`

Handles `current_issue.json` and `sprint.json`. Contributions might include:
- New state fields
- Migration utilities
- Backup/restore improvements

### CLI

Location: `src/claudesprint/cli.py`

The command-line interface. Contributions might include:
- New commands
- Better output formatting
- Interactive features

### Prompts

Location: `prompts/PROMPT_*.md`

The workflow step prompts. Contributions might include:
- Clearer instructions
- Better examples
- New workflow patterns

### Documentation

Location: `docs/`

This documentation. Contributions might include:
- New guides
- Better explanations
- More examples

## Pull Request Process

### Before Submitting

1. **Run all tests**: `pytest .claude/claudesprint/tests/`
2. **Run linting**: `ruff check .claude/claudesprint/src/`
3. **Run type checking**: `mypy .claude/claudesprint/src/claudesprint/`
4. **Test manually**: Try your changes with a real spec
5. **Update documentation**: If behavior changes

### PR Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactoring

## Testing
- [ ] Added/updated tests
- [ ] All tests pass
- [ ] Tested manually with real project

## Checklist
- [ ] Follows existing code patterns
- [ ] Backward compatible
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### Review Process

1. **Automated checks**: Tests, linting, type checking
2. **Code review**: Maintainer reviews for patterns and quality
3. **Testing**: Reviewer tests with sample project
4. **Merge**: Squash and merge to main

## Code Style

### Python

- Use type hints
- Follow PEP 8 (enforced by ruff)
- Prefer dataclasses for models
- Use pathlib for file paths

```python
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class SprintConfig:
    require_testing: bool = True
    require_browser_qa: bool = False

def load_sprint(path: Path) -> Optional[Sprint]:
    """Load sprint from JSON file."""
    if not path.exists():
        return None
    ...
```

### Markdown (Prompts)

- Clear, imperative instructions
- Use code blocks for examples
- Include "DO" and "DO NOT" sections
- Keep prompts focused on one step

### JSON (Schemas)

- Use JSON Schema draft 2020-12
- Include descriptions for all fields
- Provide sensible defaults
- Document enum values

## Releasing

For maintainers:

```bash
# Update version
# Edit pyproject.toml

# Create release commit
git add pyproject.toml
git commit -m "release: v1.2.0"

# Tag release
git tag -a v1.2.0 -m "Release 1.2.0"
git push origin main --tags
```

## Getting Help

- **Questions**: Open a discussion
- **Bugs**: Open an issue with reproduction steps
- **Features**: Open an issue to discuss first

## Recognition

Contributors are recognized in:
- CONTRIBUTORS.md
- Release notes
- Git history

Thank you for contributing to ClaudeSprint!
