# Architecture

ClaudeSprint implements a dual-loop architecture for autonomous software development.

## The Problem with Long Sessions

Traditional AI coding sessions suffer from:

- **Context accumulation** - Errors compound as conversation grows
- **Hallucination drift** - AI starts referencing non-existent code
- **Recovery difficulty** - Hard to resume after crashes
- **State ambiguity** - Unclear what's been done vs. planned

## The Solution: Fresh Sessions + Structured State

ClaudeSprint solves this by:

1. Running each workflow step in a **fresh Claude session**
2. Passing state through **validated JSON artifacts**
3. Using **schema validation** at every handoff
4. Maintaining **recovery checkpoints** automatically

## Dual-Loop Design

![ClaudeSprint Dual-Loop Architecture](../assets/loop-detailed.jpg)

## Sprint Loop (Outer)

The sprint loop manages project-level orchestration:

| Step | Purpose |
|------|---------|
| Load Sprint | Read `sprint.json` with all issues |
| Get Bearings | Summarize progress, identify blockers |
| Select Issue | Agent picks next issue by priority/dependencies |
| Create Issue State | Initialize `current_issue.json` |
| Run Issue Loop | Execute the inner loop |
| Mark Complete | Update sprint, clear issue state |

## Issue Loop (Inner)

Each issue goes through a structured workflow:

| Step | Purpose | Model |
|------|---------|-------|
| `read-docs` | Gather relevant documentation | Sonnet |
| `implement` | Write the code | **Opus** |
| `write-tests` | Create tests for acceptance criteria | Sonnet |
| `run-tests` | Execute test suite | Sonnet |
| `fix-tests` | Debug failing tests | **Opus** |
| `browser-validation` | E2E UI testing (if applicable) | Sonnet |
| `code-review` | Automated review against spec | **Opus** |
| `fix-code-review-issues` | Address review feedback | Opus |
| `update-docs` | Update documentation | Sonnet |
| `stage-changes` | Git add changed files | Sonnet |
| `commit-changes` | Create commit | Sonnet |

## State Artifacts

### sprint.json

Source of truth for all issues:

```json
{
  "spec_id": "SPEC_01",
  "issues": [
    {
      "id": "SPEC_01-001",
      "title": "Implement URL shortening",
      "status": "completed",
      "acceptance_criteria": ["..."]
    }
  ]
}
```

### current_issue.json

Active issue being worked on:

```json
{
  "issue_id": "SPEC_01-002",
  "current_step": "implement",
  "retry_count": 0,
  "context": {
    "files_read": ["src/api.ts"],
    "implementation_notes": "..."
  }
}
```

## Recovery & Resilience

ClaudeSprint handles failures gracefully:

- **Automatic checkpoints** after each step
- **Retry logic** with configurable limits
- **State validation** prevents corruption
- **File backups** before modifications

Resume after any interruption:

```bash
claudesprint run  # Continues from last checkpoint
```

## Model Selection

ClaudeSprint optimizes cost by using appropriate models:

- **Opus** for critical decisions (implement, fix, review)
- **Sonnet** for structured tasks (tests, docs, git)

Override with:

```bash
CLAUDESPRINT_MODEL_OVERRIDE=sonnet claudesprint run
```
