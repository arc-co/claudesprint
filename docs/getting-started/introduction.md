# Introduction to ClaudeSprint

## What is ClaudeSprint?

ClaudeSprint is an **autonomous software development orchestrator** that transforms Claude Code from a conversational assistant into a disciplined, self-managing development agent. It implements a structured workflow that takes a project specification and systematically delivers working, tested code—issue by issue—without constant human supervision.

At its core, ClaudeSprint is a **Dual-Loop Architecture**:

```
┌─────────────────────────────────────────────────────────────────┐
│                     SPRINT LOOP (Outer)                         │
│  Manages the overall sprint: selects issues, tracks progress    │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                  ISSUE LOOP (Inner)                     │   │
│   │  Executes one issue through all workflow steps:         │   │
│   │  implement → test → review → commit → complete          │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  On completion: mark done, select next issue, repeat           │
└─────────────────────────────────────────────────────────────────┘
```

The **Sprint Loop** handles project management—deciding which issue to work on next based on dependencies, priority, and context continuity. The **Issue Loop** handles execution—taking a single issue through implementation, testing, code review, and commit.

## Opinionated Agile: How This Differs from Native Claude Code

Claude Code is a powerful general-purpose assistant. You can ask it anything, and it will help. But this flexibility comes with a cost: without structure, Claude Code sessions tend toward **vibe coding**—conversational development where the human remains in the loop for every decision, there's no enforced quality gates, and context gets lost between sessions.

ClaudeSprint takes a fundamentally different approach. It implements **Extreme Programming (XP) principles** in an automated workflow. To understand how this prevents vibe coding through disciplined specifications, see [Specifications and Scoping](../guides/specifications-and-scoping.md).

| XP Principle | ClaudeSprint Implementation |
|--------------|----------------------------|
| **Small Batches** | One issue per cycle, clear acceptance criteria |
| **Test-Driven Development** | `write-tests` step before `run-tests`, tests must pass to proceed |
| **Continuous Integration** | Commits only after all gates pass (tests, lint, review) |
| **Collective Ownership** | Fresh session per step prevents context coupling |
| **Sustainable Pace** | Automatic model selection optimizes cost |

### The Key Difference

**Native Claude Code:** "Hey Claude, can you help me build a user authentication system?"

**ClaudeSprint:** A specification file defines exactly what "user authentication" means—with acceptance criteria for each issue. The agent works autonomously through each issue, running tests, performing code review, and only committing when quality gates pass. You check in when it's done, not at every keystroke.

This is an orchestrator for **shipping reliable software**, not a chat interface for exploring ideas.

## Template vs. Package: The Ownership Model

ClaudeSprint is distributed as a **template**, not a package. When you install it, you're copying the entire `.claude/claudesprint/` directory into your project. You own this code.

### Why a Template?

Traditional packages create abstraction barriers. You depend on upstream decisions, fight against conventions that don't fit your project, and submit PRs for customizations that only matter to you.

ClaudeSprint inverts this model:

```
Package Model (NOT ClaudeSprint):
┌──────────────────────────────────────────────┐
│  Your Project                                │
│  ┌────────────────────────────────────────┐  │
│  │  node_modules/claudesprint (locked)    │  │
│  │  - You can't modify this               │  │
│  │  - Upstream controls behavior          │  │
│  │  - Updates may break your workflows    │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘

Template Model (ClaudeSprint):
┌──────────────────────────────────────────────┐
│  Your Project                                │
│  ┌────────────────────────────────────────┐  │
│  │  .claude/claudesprint/ (YOU OWN THIS)  │  │
│  │  - Modify prompts for your team        │  │
│  │  - Add project-specific steps          │  │
│  │  - Customize without asking permission │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

### Practical Benefits

1. **Deep Customization**: Change `PROMPT_implement.md` to enforce your team's coding standards
2. **Project-Specific Steps**: Add a `PROMPT_security-audit.md` step for fintech projects
3. **No Upgrade Anxiety**: You control when (or if) you adopt upstream changes
4. **Debuggability**: Everything is readable Python and Markdown—no black boxes

### The Trade-off

You're responsible for maintenance. If the upstream template adds a feature you want, you merge it manually. This is intentional: ClaudeSprint prioritizes **control over convenience**.

## Core Philosophy

### 1. Fresh Session Per Step

Each workflow step runs in a fresh Claude session. This prevents context pollution—the hallucinations that accumulate when a session gets too long. The trade-off (no memory between steps) is solved by explicit state files (`current_issue.json`, `sprint.json`).

### 2. Validation Gates

The agent cannot progress until quality checks pass:
- Tests must succeed before code review
- Code review must pass before commit
- Commits only happen with clean state

### 3. Immutable Specifications

The `sprint.json` issues are contracts. The agent can't redefine what "done" means mid-implementation. If requirements genuinely change, that's a planning step, not an implementation detail.

### 4. Agent-Driven Decisions

Within the rules, the agent makes decisions autonomously. It chooses which issue to work on next. It decides how to implement acceptance criteria. It determines if a test failure is a code bug or a test bug. Human intervention is for exceptions, not routine work.

## When to Use ClaudeSprint

**Good fit:**
- Greenfield projects with clear specifications
- Feature development with defined acceptance criteria
- Teams that value automated quality gates
- Projects where you want to "set it and forget it"

**Not a good fit:**
- Exploratory research or prototyping (use native Claude Code)
- Highly ambiguous requirements (write specs first)
- Projects requiring constant human judgment calls
- Quick one-off changes (overkill for small tasks)

## Next Steps

- [Installation](./installation.md): Set up ClaudeSprint in your project
- [Quickstart](./quickstart.md): See it in action with a demo
- [Architecture](../concepts/architecture.md): Deep dive into the dual-loop system
