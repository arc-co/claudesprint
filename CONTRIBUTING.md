# Contributing to ClaudeSprint

Thank you for your interest in contributing to ClaudeSprint. This guide explains how to contribute to different parts of the project.

## Project Structure

ClaudeSprint has two distinct components:

```
.claude/claudesprint/          # Core engine (the workflow system)
.claude/claudesprint/specs/    # Example specifications
```

**Core Engine** (`/.claude/claudesprint/`): The Python package, prompts, schemas, and configuration that power the workflow.

**Example Specs** (`.claude/claudesprint/specs/examples/`): Sample specifications demonstrating how to use ClaudeSprint.

## How to Contribute

### Contributing to the Core Engine

The core engine lives in `.claude/claudesprint/`. If you want to improve the workflow system itself:

1. **Fork the repository** and create a feature branch
2. **Make your changes** to the engine code
3. **Test thoroughly** - run existing tests and add new ones
4. **Submit a pull request** with a clear description of the change

#### What belongs in core engine PRs:
- Bug fixes in the Python CLI (`src/claudesprint/`)
- Improvements to workflow prompts (`prompts/`)
- Schema updates (`schemas/`)
- Documentation improvements
- New CLI commands or options
- Performance improvements

#### Guidelines for engine changes:
- Maintain backwards compatibility when possible
- Update schemas and validation if changing JSON formats
- Add tests for new functionality
- Update CLAUDE.md if changing workflow behavior

### Contributing Example Specifications

Want to share a spec that demonstrates ClaudeSprint capabilities?

1. Create your spec in `.claude/claudesprint/specs/examples/`
2. Ensure it follows the spec format (see existing examples)
3. Test it with `claudesprint init` and `claudesprint run`
4. Submit a PR with the spec and any supporting files

### Reporting Issues

- Use GitHub Issues for bug reports and feature requests
- Include ClaudeSprint version (`claudesprint --version`)
- Include relevant logs from `.claude/claudesprint/project/current_issue.log`
- Describe steps to reproduce

## Governance: Vendored vs. Modifiable Code

### For Users of ClaudeSprint

The `.claude/claudesprint/` directory is designed as **vendored library code**. This means:

**Recommended approach:**
- Treat `.claude/claudesprint/` as read-only in your projects
- Configure behavior through `.claude/claudesprint/config/` files
- Write your specs in `.claude/claudesprint/specs/`
- Use the CLI interface (`claudesprint` commands)

**When you might modify claudesprint:**
- You need behavior not achievable through configuration
- You're experimenting with workflow changes
- You want to contribute improvements upstream

**If you modify claudesprint locally:**
- Your changes may conflict with future updates
- Consider whether your change should be a PR instead
- Document your modifications for your team

### Updating ClaudeSprint

Since claudesprint is vendored, updates require manual effort:

```bash
# Option 1: Replace entirely (loses local changes)
rm -rf .claude/claudesprint
# Copy new version from upstream

# Option 2: Merge updates (preserves local changes)
# Use git to merge upstream changes
```

We recommend keeping claudesprint unmodified and submitting improvements as PRs.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/your-org/claudesprint.git
cd claudesprint

# Run setup
./setup.sh

# Activate environment
source .venv/bin/activate

# Verify
claudesprint status
```

### Running Tests

```bash
# Run claudesprint's tests
cd .claude/claudesprint
pytest

# Run with coverage
pytest --cov=src/claudesprint
```

## Pull Request Process

1. **Create an issue first** for significant changes
2. **Fork and branch** - use descriptive branch names
3. **Make focused changes** - one feature/fix per PR
4. **Test your changes** - include tests when applicable
5. **Update documentation** - CLAUDE.md, README, etc.
6. **Submit the PR** with a clear description

### PR Title Convention

Use conventional commits style:
- `feat: add new workflow step`
- `fix: correct schema validation`
- `docs: update contributing guide`
- `refactor: simplify CLI parsing`

## Code of Conduct

Be respectful and constructive. We're all here to build something useful together.

## Questions?

- Open a GitHub Discussion for general questions
- Open an Issue for bugs or feature requests
- Check existing issues before creating new ones

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
