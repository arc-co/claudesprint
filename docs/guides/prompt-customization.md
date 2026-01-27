# Prompt Customization

ClaudeSprint uses markdown-based prompts to guide the AI agent through each workflow step. You can customize these prompts to match your project's coding standards, conventions, and specific requirements.

## Prompt Hierarchy

ClaudeSprint loads prompts from three locations in priority order:

| Priority | Location | Purpose |
|----------|----------|---------|
| 1 (highest) | `.claudesprint/prompts/` | Project-specific customizations |
| 2 | `~/.config/claudesprint/prompts/` | User-wide defaults |
| 3 (lowest) | Package defaults | Built-in prompts |

When a prompt is requested, ClaudeSprint checks each location in order and uses the first match found.

### Example Resolution

If your project requests the `implement` prompt:

1. Check `.claudesprint/prompts/PROMPT_implement.md` - if exists, use it
2. Check `~/.config/claudesprint/prompts/PROMPT_implement.md` - if exists, use it
3. Use the package default from `claudesprint/prompts/PROMPT_implement.md`

## Available Prompt Files

Each workflow step has a corresponding prompt file:

| Step | Filename | Purpose |
|------|----------|---------|
| init | `PROMPT_init.md` | Sprint initialization from spec |
| plan | `PROMPT_plan.md` | Sprint planning and issue generation |
| select-issue | `PROMPT_select-issue.md` | Choosing the next issue to work on |
| read-docs | `PROMPT_read-docs.md` | Gathering context and documentation |
| implement | `PROMPT_implement.md` | Writing code changes |
| write-tests | `PROMPT_write-tests.md` | Creating tests for acceptance criteria |
| run-tests | `PROMPT_run-tests.md` | Executing the test suite |
| fix-tests | `PROMPT_fix-tests.md` | Fixing failing tests |
| browser-validation | `PROMPT_browser-validation.md` | E2E UI testing |
| code-review | `PROMPT_code-review.md` | Reviewing code against spec |
| fix-code-review-issues | `PROMPT_fix-code-review-issues.md` | Addressing review feedback |
| update-docs | `PROMPT_update-docs.md` | Updating documentation |
| stage-changes | `PROMPT_stage-changes.md` | Staging files for commit |
| commit-changes | `PROMPT_commit-changes.md` | Creating git commits |

Additionally, `_common.md` contains shared patterns included in all prompts.

## Creating Custom Prompts

### Project-Level Customization

To customize prompts for a specific project:

```bash
# Initialize the project (creates .claudesprint/prompts/)
claudesprint initrepo

# Copy a prompt to customize
cp ~/.local/lib/python*/site-packages/claudesprint/prompts/PROMPT_implement.md \
   .claudesprint/prompts/PROMPT_implement.md

# Or create from scratch
cat > .claudesprint/prompts/PROMPT_implement.md << 'EOF'
# Step: implement

Your custom implementation prompt...
EOF
```

### User-Level Customization

To set defaults for all your projects:

```bash
# Create the global prompts directory
mkdir -p ~/.config/claudesprint/prompts

# Copy prompts to customize
cp ~/.local/lib/python*/site-packages/claudesprint/prompts/PROMPT_code-review.md \
   ~/.config/claudesprint/prompts/PROMPT_code-review.md
```

## Jinja2 Template Variables

Prompts are rendered as Jinja2 templates, giving you access to context variables:

### Built-in Variables

| Variable | Type | Description |
|----------|------|-------------|
| `browser_validation_enabled` | bool | True if `agent-browser` is installed |
| `context7_available` | bool | True if `context7` CLI is available |

### Using Variables in Prompts

```markdown
# Step: browser-validation

{% if browser_validation_enabled %}
## Browser Testing

Use agent-browser to validate UI:

```bash
agent-browser open http://localhost:3000
agent-browser snapshot -i
```
{% else %}
## Browser Testing (Skipped)

agent-browser is not installed. Skipping browser validation.
Set `browser_validation_enabled: false` in sprint config.
{% endif %}
```

### Conditional Sections

```markdown
{% if context7_available %}
## Documentation Lookup

Use context7 to check library documentation:

```bash
context7 query "React useEffect cleanup"
```
{% endif %}
```

## Prompt Structure Best Practices

### Required Sections

Most prompts should include:

1. **Title** - Clear step name
2. **Get Bearings** - Bash commands to read current state
3. **Main Instructions** - What to do in this step
4. **Update current_issue.json** - Fields to update
5. **Log & Exit** - Logging and termination
6. **Rules** - Constraints (what NOT to do)

### Example Prompt Structure

```markdown
# Step: my-custom-step

You are a [role description]. [One sentence about the step's purpose].

## Get Bearings

```bash
pwd
cat .claudesprint/state/current_issue.json
# ... standard context gathering
```

Extract: `issue_id`, `issue_title`, [other relevant fields]

## [Main Section Name]

1. First instruction
2. Second instruction
3. Third instruction

### Subsection (if needed)

Additional details...

## Update current_issue.json

- Set `step` to `next-step`
- Set `goal` to describe next action
- Add to `changes`: modified files
- Add to `rationale`: key decisions

## Log & Exit

```bash
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] STEP: my-custom-step -> next-step" >> .claudesprint/state/current_issue.log
```

## Rules

- Do NOT [forbidden action 1]
- Do NOT [forbidden action 2]
- [Important constraint]
```

### Termination Tokens

Some steps use termination tokens to signal outcomes:

| Token | Meaning |
|-------|---------|
| `STATUS: PASS` | Step completed successfully |
| `STATUS: FAIL` | Step failed (generic) |
| `STATUS: FAIL_CODE` | Code bug detected |
| `STATUS: FAIL_TEST` | Test bug detected |
| `STATUS: SKIP` | Step skipped (not applicable) |
| `STATUS: ISSUES` | Issues found requiring fixes |

## Common Customizations

### Adding Coding Standards

Modify `PROMPT_implement.md` to include your team's standards:

```markdown
## Coding Standards

- Use TypeScript strict mode
- All functions must have JSDoc comments
- Use `const` over `let` when possible
- Prefer async/await over .then() chains
- Maximum file length: 300 lines
```

### Adding Test Requirements

Modify `PROMPT_write-tests.md`:

```markdown
## Test Requirements

- Minimum 80% coverage for new code
- Use Jest with React Testing Library
- Mock all external API calls
- Include edge cases and error scenarios
```

### Adding Review Criteria

Modify `PROMPT_code-review.md`:

```markdown
## Review Checklist

- [ ] No TODO comments without issue links
- [ ] No console.log statements
- [ ] Error handling for all async operations
- [ ] Accessibility attributes on interactive elements
```

## Debugging Prompts

### Check Which Prompt Is Being Used

```python
from claudesprint.services.path_service import PathService
from claudesprint.services.prompt_service import PromptService

path_service = PathService()
prompt_service = PromptService(path_service)

# Check source for a specific prompt
source = prompt_service.prompt_source("implement")
print(f"implement prompt loaded from: {source}")
# Output: "project", "global", or "package"
```

### View Rendered Content

```python
content = prompt_service.get_prompt_content("implement")
print(content)
```

### Check Context Variables

```python
context = prompt_service.context
print(f"browser_validation_enabled: {context.browser_validation_enabled}")
print(f"context7_available: {context.context7_available}")
```

## Tips

1. **Start minimal** - Only customize prompts that need changes
2. **Keep the structure** - Maintain standard sections for consistency
3. **Test changes** - Run a sprint with modified prompts to verify behavior
4. **Version control** - Commit project-level prompts with your code
5. **Document customizations** - Add comments explaining why you customized

## Next Steps

- [Workflow Steps](../concepts/workflow-steps.md): Understand each step in detail
- [Configuration](./configuration.md): Other customization options
- [CLI Commands](../reference/cli-commands.md): Command reference
