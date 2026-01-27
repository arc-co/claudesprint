# Specifications and Scoping

Writing effective specifications is the most important skill for ClaudeSprint success. This guide covers the philosophy, techniques, and common pitfalls of scoping work for an autonomous agent.

## The "Anti-Vibe Coding" Mindset

ClaudeSprint is an **orchestrator**, not a magic wand. The quality of output directly correlates with the quality of input. Vague specifications produce vague implementations.

### Vibe Coding vs. Specification-Driven Development

**Vibe Coding** (what ClaudeSprint prevents):
```
Human: "Make me a user authentication system"
AI: [implements something]
Human: "No, I meant OAuth, not username/password"
AI: [starts over]
Human: "Actually, can we also add 2FA?"
AI: [scope creep begins]
Human: "This isn't quite what I wanted..."
[endless iteration]
```

**Specification-Driven Development** (ClaudeSprint approach):
```
Spec: "User Authentication System"
- Feature 1: OAuth Login
  - Acceptance: User can log in with Google OAuth
  - Acceptance: User can log in with GitHub OAuth
  - Acceptance: OAuth state is validated to prevent CSRF
- Feature 2: Session Management
  - Acceptance: Session token expires after 24 hours
  - Acceptance: User can manually log out
[Agent implements exactly this, no more, no less]
```

### The Specification as Contract

Your specification is a **contract** between you and the agent:

1. **You promise**: Clear, testable acceptance criteria
2. **Agent promises**: Implementation satisfying exactly those criteria
3. **Neither side**: Changes requirements mid-implementation

If you realize the spec is wrong during implementation, that's a **planning failure**, not an implementation detail. Stop the sprint, update the spec, re-initialize.

## One Sprint = One Feature

### The Scope Principle

Each sprint should represent a **coherent unit of work** that can be completed autonomously:

**Good Sprint Scope**:
- "User Authentication for MVP" (focused feature)
- "Shopping Cart Functionality" (bounded feature)
- "API Rate Limiting" (infrastructure improvement)
- "Fix Critical Checkout Bugs" (defined problem set)

**Bad Sprint Scope**:
- "Build the whole app" (too large, undefined)
- "Improve performance" (too vague, no criteria)
- "Various fixes and updates" (unfocused)
- "Refactor everything" (unbounded)

### Sizing Issues

Each issue within a sprint should be:
- **Completable in one session** (typically 30-60 minutes of agent work)
- **Independently testable** (has clear acceptance criteria)
- **Atomic** (doesn't leave the codebase in a broken state)

```markdown
## Good Issue Size

### Feature: Add to Cart Button
- User can click "Add to Cart" on product page
- Cart count in header updates immediately
- Toast notification confirms addition

## Too Large

### Feature: Shopping Cart
- Add to cart
- Remove from cart
- Update quantities
- Calculate totals
- Apply discounts
- Checkout flow
- Payment processing
[This should be 5-7 separate issues]

## Too Small

### Feature: Button Styling
- Button has blue background
[Combine with functional implementation]
```

## Context Loading: The Upfront Investment

The agent cannot read your mind. It starts each session with only:
- The specification file
- `current_issue.json` context
- What it can read from the codebase

### Provide Explicit Context

**Bad Specification** (context-free):
```markdown
## Feature: User Profile Page
- Display user information
- Allow editing profile
```

**Good Specification** (context-rich):
```markdown
## Feature: User Profile Page

### Technical Context
- **Framework**: Next.js 14 App Router
- **Styling**: Tailwind CSS (see existing components in `src/components/`)
- **State Management**: React Query for server state
- **API**: REST endpoints at `/api/users/*`
- **Auth**: Use existing `useAuth()` hook from `src/hooks/useAuth.ts`

### Existing Patterns to Follow
- Form components: See `src/components/forms/ContactForm.tsx`
- API calls: See `src/services/api.ts` for fetch wrapper
- Validation: Use Zod schemas from `src/schemas/`

### Acceptance Criteria
- Display user's name, email, avatar from `/api/users/me`
- Avatar upload using existing `ImageUpload` component
- Form validation matches existing patterns
- Loading states use existing `Skeleton` component
- Errors display using existing `Toast` component
```

### Specify Dependencies and Versions

**Bad**:
```markdown
Use a form library for validation
```

**Good**:
```markdown
Use React Hook Form (already installed, v7.x) with Zod resolver for validation.
See existing implementation in `src/components/forms/LoginForm.tsx`.
```

### Reference Existing Code

Don't make the agent guess about patterns:

```markdown
### Implementation Notes

Follow the pattern established in:
- **Components**: `src/components/Dashboard/DashboardCard.tsx` for card layout
- **API hooks**: `src/hooks/useUsers.ts` for data fetching pattern
- **Tests**: `src/components/Dashboard/__tests__/` for test structure

Do NOT:
- Create new utility functions (use existing in `src/utils/`)
- Add new dependencies without explicit approval
- Change the existing API response format
```

## Writing Acceptance Criteria

Acceptance criteria are the **testable statements** that define "done". They're the foundation of ClaudeSprint's quality gates.

### The SMART Criteria for Criteria

Each acceptance criterion should be:

- **Specific**: Exactly one behavior or outcome
- **Measurable**: Can be verified with a test
- **Achievable**: Possible given the codebase
- **Relevant**: Actually matters for the feature
- **Testable**: Automated test can verify it

### Good vs. Bad Criteria

| Bad Criterion | Why It's Bad | Good Criterion |
|---------------|--------------|----------------|
| "Works correctly" | Vague, untestable | "Returns 200 with user data for valid token" |
| "Looks nice" | Subjective | "Uses existing `Card` component with `shadow-lg` class" |
| "Fast performance" | No threshold | "API response under 200ms for cached data" |
| "Handles errors" | Too broad | "Returns 401 for expired tokens with error message" |
| "User-friendly" | Subjective | "Displays loading spinner during fetch" |

### Criterion Templates

**API Behavior**:
```markdown
- POST `/api/resource` returns 201 with created resource
- POST `/api/resource` returns 400 with validation errors for invalid input
- GET `/api/resource/:id` returns 404 for non-existent resource
```

**UI Behavior**:
```markdown
- Button is disabled during form submission
- Error message appears below invalid field
- Success toast appears after form submission
- Form resets after successful submission
```

**State Management**:
```markdown
- Counter increments when button clicked
- Counter never goes below 0
- Counter value persists across page navigation
```

## Scoping for Existing Applications

When adding features to large existing codebases, precise scoping is even more critical.

### The Surgical Approach

```markdown
## Feature: Add Export Button to Dashboard

### Scope Boundaries

**In Scope**:
- Add "Export" button to `src/pages/Dashboard.tsx`
- Create `exportData()` function in `src/utils/export.ts`
- CSV format only

**Explicitly Out of Scope**:
- Changes to Dashboard layout
- Other export formats (PDF, Excel)
- Backend API changes
- Data transformation logic

### Files to Modify
1. `src/pages/Dashboard.tsx` - Add button
2. `src/utils/export.ts` - Create new file
3. `src/pages/Dashboard.test.tsx` - Add test

### Files NOT to Modify
- Any files in `src/components/` (use existing components only)
- Any API files
- Any other pages
```

### Dependency Mapping

For complex features, map out what the agent can and cannot touch:

```markdown
### Dependency Analysis

**Can Use** (existing, stable):
- `useAuth()` hook
- `Button` component
- `fetchApi()` utility
- User TypeScript types from `@/types`

**Must Create**:
- `ExportButton` component
- `exportToCsv()` utility

**Cannot Modify**:
- Auth system
- API layer
- Database schema
- Build configuration
```

## Common Pitfalls

### 1. The Kitchen Sink Spec

**Problem**: Trying to specify an entire application in one sprint.

**Symptom**: Sprint has 50+ issues, agent gets confused about priorities.

**Solution**: Break into multiple sprints. Each sprint = one epic/feature.

### 2. The Vague Handwave

**Problem**: "Make it work like the old system"

**Symptom**: Agent guesses wrong, implements something different.

**Solution**: Document exactly what "the old system" does. Reference specific behaviors.

### 3. The Moving Target

**Problem**: Changing requirements during implementation.

**Symptom**: Agent gets stuck in loops, context gets corrupted.

**Solution**: Stop sprint, update spec, re-initialize. Don't patch mid-flight.

### 4. The Assumed Context

**Problem**: "Use the usual patterns"

**Symptom**: Agent uses different patterns, inconsistent code.

**Solution**: Explicitly reference files that demonstrate patterns.

### 5. The Missing Negative Cases

**Problem**: Only specifying happy paths.

**Symptom**: No error handling, crashes on edge cases.

**Solution**: Include acceptance criteria for error states, edge cases, boundaries.

## Specification Template

```markdown
# [Feature/Project Name]

## Overview
[2-3 sentences describing what this sprint will deliver]

## Technical Context
- **Stack**: [Framework, language versions]
- **Key Dependencies**: [Libraries being used]
- **Relevant Existing Code**: [Paths to reference implementations]

## Features

### Feature 1: [Name]
[1 sentence description]

**Acceptance Criteria**:
- [Testable criterion 1]
- [Testable criterion 2]
- [Error case criterion]

**Technical Notes**:
- [Pattern to follow]
- [File references]

### Feature 2: [Name]
...

## Scope Boundaries

**In Scope**:
- [Explicit list]

**Out of Scope**:
- [Explicit list]

## Dependencies Between Features
- Feature 2 depends on Feature 1
- Feature 3 can be done in parallel with Feature 2

## Testing Requirements
- Unit tests required for all business logic
- Integration tests for API endpoints
- [Browser tests required/not required]
```

## Next Steps

- [Configuration](./configuration.md): Set up hooks for your stack
- [Advanced Workflows](./advanced-workflows.md): Running parallel sprints
- [Quickstart](../getting-started/quickstart.md): Try a spec with the demo
