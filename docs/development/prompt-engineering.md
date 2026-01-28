# Prompt Engineering

ClaudeSprint's behavior is defined by prompt files in `.claudesprint/prompts/`. Customizing these prompts allows you to tailor the workflow to your team's needs, coding standards, and project requirements.

## Prompt Architecture

### How Prompts Work

Each workflow step has a corresponding prompt file:

```
prompts/
├── PROMPT_init.md              # Sprint initialization
├── PROMPT_plan.md              # Sprint planning/updates
├── PROMPT_select-issue.md      # Issue selection
├── PROMPT_read-docs.md         # Documentation gathering
├── PROMPT_implement.md         # Code implementation
├── PROMPT_write-tests.md       # Test creation
├── PROMPT_run-tests.md         # Test execution
├── PROMPT_fix-tests.md         # Test failure analysis
├── PROMPT_browser-validation.md # Browser testing
├── PROMPT_code-review.md       # Code review
├── PROMPT_fix-code-review-issues.md # Review fixes
├── PROMPT_update-docs.md       # Documentation updates
├── PROMPT_stage-changes.md     # Git staging
├── PROMPT_commit-changes.md    # Git commits
└── PROMPT_complete-issue.md    # Issue completion
```

### Prompt Loading

When a step runs:
1. Workflow reads `current_issue.json` to determine step
2. Loads corresponding `PROMPT_<step>.md`
3. Combines with CLAUDE.md context
4. Sends to Claude API
5. Agent executes instructions

### Context Injection

Prompts have access to:
- `CLAUDE.md` (always loaded)
- `current_issue.json` (via "Get Bearings")
- `sprint.json` (via "Get Bearings")
- Recent log entries (last 20 lines)

## Prompt Structure

### Standard Template

```markdown
# Step Name

## Context
You are in the `step-name` step of the ClaudeSprint workflow.

## Goal
[1-2 sentences describing what this step accomplishes]

## Pre-flight Checks
1. Verify current_issue.json exists
2. Verify step is `step-name`
3. [Step-specific prerequisites]

## Instructions
[Detailed, numbered instructions]

## DO
- [Explicit things to do]

## DO NOT
- [Explicit things to avoid]

## Output State
Update current_issue.json with:
- `step`: [next step]
- [other fields to update]

## Examples
[Optional: Show example inputs/outputs]
```

### Key Sections

#### Context

Orients the agent to the current step:

```markdown
## Context
You are in the `implement` step. Your task is to write code
that satisfies the acceptance criteria in current_issue.json.
```

#### Pre-flight Checks

Ensures prerequisites are met before proceeding:

```markdown
## Pre-flight Checks
1. Read current_issue.json - verify step is "implement"
2. Read sprint.json - verify issue exists and is in_progress
3. Check that read-docs completed (context has findings)
```

#### Instructions

Step-by-step guidance:

```markdown
## Instructions

1. Read the acceptance criteria from context.acceptance_criteria
2. Review the context from the read-docs step
3. Identify files to modify based on context and session log
4. Make minimal code changes:
   - Follow existing patterns
   - Don't add unrequested features
   - Handle only specified error cases
5. Update current_issue.json with changes made
6. Set step to "write-tests"
```

#### DO / DO NOT

Explicit boundaries:

```markdown
## DO
- Follow patterns from files mentioned in context/session log
- Make the minimum changes to satisfy criteria
- Record all changes in current_issue.json

## DO NOT
- Add features not in acceptance criteria
- Refactor unrelated code
- Add "nice to have" error handling
- Create new utility functions for one-time use
```

## Customization Examples

### Enforce Coding Standards

Add to `PROMPT_implement.md`:

```markdown
## Code Standards

All code must follow these standards:

### TypeScript
- Use explicit return types on all functions
- Prefer `const` over `let`
- Use `interface` over `type` for object shapes
- No `any` types without explicit justification

### React
- Use functional components only
- Prefer custom hooks over inline logic
- Props interfaces must be exported
- Components must have displayName
```

### Add Security Requirements

Add to `PROMPT_code-review.md`:

```markdown
## Security Checklist

Before approving, verify:

### Input Validation
- [ ] User input is validated before use
- [ ] SQL queries use parameterization
- [ ] File paths are sanitized

### Authentication
- [ ] Protected routes check auth state
- [ ] Tokens are not logged or exposed
- [ ] Session handling follows best practices

### Data Handling
- [ ] Sensitive data is not in client bundles
- [ ] Error messages don't leak internals
- [ ] Rate limiting is in place for APIs
```

### Customize Test Requirements

Modify `PROMPT_write-tests.md`:

```markdown
## Testing Requirements

### Unit Tests
- One test file per source file
- Use describe/it structure
- Minimum 80% coverage
- Mock external dependencies

### Test Naming
- `it('should [expected behavior] when [condition]')`
- Group related tests in describe blocks
- Use clear, descriptive names

### Required Tests
For each acceptance criterion:
- Happy path test
- Edge case tests (null, empty, boundary)
- Error case tests
```

### Add Domain-Specific Checks

For a fintech project, add to `PROMPT_code-review.md`:

```markdown
## Financial Calculations

When reviewing code that handles money:
- [ ] Uses decimal types, not floating point
- [ ] Rounding is explicit and documented
- [ ] Currency is always specified
- [ ] Calculations have unit tests with known values
- [ ] Edge cases (zero, negative, overflow) are handled
```

## Prompt Variables

### Using Issue Context

Reference values from `current_issue.json`:

```markdown
## Instructions

1. Review acceptance criteria:
   ${context.acceptance_criteria}

2. Check issue category:
   ${context.category}

3. Consider previous context:
   ${context}
```

### Conditional Sections

Some prompts have conditional behavior:

```markdown
## Browser Validation

### Skip Conditions
If category is NOT in [ui, feature]:
- Log "Skipping browser validation - not a UI issue"
- Set step to "code-review"
- Exit

### Run Conditions
If category IS in [ui, feature]:
- Proceed with validation steps below
```

## Prompt Best Practices

### 1. Be Explicit

Vague instructions lead to inconsistent behavior:

```markdown
# Bad
Review the code and fix any issues.

# Good
Review each acceptance criterion and verify:
1. Code implements the criterion exactly
2. No additional functionality was added
3. Tests exist for the criterion
4. Code follows patterns from context
```

### 2. Use Checklists

Checklists ensure completeness:

```markdown
## Completion Checklist
- [ ] All acceptance criteria implemented
- [ ] Tests written for each criterion
- [ ] No scope creep
- [ ] Changes logged in current_issue.json
- [ ] Next step set correctly
```

### 3. Provide Examples

Examples clarify intent:

```markdown
## Commit Message Format

Example:
```
feat(auth): implement OAuth login flow

- Add Google OAuth provider
- Add GitHub OAuth provider
- Add session management

Acceptance Criteria:
- [x] User can log in with Google
- [x] User can log in with GitHub
- [x] Session persists across page refreshes
```
```

### 4. Include Failure Handling

Tell the agent what to do when things go wrong:

```markdown
## Error Handling

If tests fail:
1. Analyze the failure message
2. Determine if it's a code bug or test bug
3. Update current_failures with analysis
4. Set step to "fix-tests" (not back to implement!)
5. Increment retry_count
```

### 5. Maintain State Consistency

Ensure state updates are complete:

```markdown
## State Updates

Update current_issue.json with:
- `step`: "write-tests"
- `changes`: Add all files modified
- `commands_run`: Add any commands executed
- `current_failures`: Clear if previously set
- Log key decisions to `current_issue.log`
```

## Testing Prompt Changes

### Manual Testing

```bash
# Make your prompt change
vim .claudesprint/prompts/PROMPT_implement.md

# Create test project
mkdir /tmp/prompt-test
cd /tmp/prompt-test
# ... setup project ...

# Run with your changes
claudesprint run -n 3

# Check behavior
cat .claudesprint/project/current_issue.log
```

### A/B Testing

Test prompt variations:

```bash
# Save original
cp prompts/PROMPT_implement.md prompts/PROMPT_implement.md.bak

# Try variation A
cp prompts/PROMPT_implement_v2.md prompts/PROMPT_implement.md
claudesprint run -n 3
# Evaluate results

# Try variation B
cp prompts/PROMPT_implement_v3.md prompts/PROMPT_implement.md
claudesprint run -n 3
# Evaluate results

# Restore best version
cp prompts/PROMPT_implement_best.md prompts/PROMPT_implement.md
```

### Metrics to Track

- **Step completion rate**: How often does the step succeed?
- **Retry frequency**: How often does the step need retries?
- **Output quality**: Does the code meet your standards?
- **Time to completion**: Is the step faster or slower?

## Prompt Version Control

Track prompt changes with git:

```bash
# Create a meaningful commit
git add prompts/PROMPT_implement.md
git commit -m "prompts(implement): add TypeScript strict mode requirements"

# Tag working versions
git tag prompt-v1.0
```

Consider a CHANGELOG for prompts:

```markdown
# Prompt Changelog

## 2026-01-24
- PROMPT_implement.md: Added TypeScript strict mode requirements
- PROMPT_code-review.md: Added security checklist

## 2026-01-20
- PROMPT_write-tests.md: Increased coverage requirement to 80%
```

## Next Steps

- [Engine Internals](./engine-internals.md): How prompts are loaded and executed
- [Contributing](./contributing.md): Submit prompt improvements
- [Workflow Steps](../concepts/workflow-steps.md): Understand what each step does
