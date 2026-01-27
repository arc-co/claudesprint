# Example Specifications

This folder contains example specification files to help you understand how to write specs for the ClaudeSprint workflow.

## Examples

- **textbook-exchange-mvp.md** - A comprehensive example of a web application MVP spec (Node/Express, SQLite, HTMX)
- **textbook-exchange-tests.md** - A follow-up spec focused on adding tests to an existing implementation

## Using These Examples

1. Review the examples to understand the spec structure
2. Copy `../template.md` as a starting point for your own spec
3. Place your spec in the parent `specs/` directory (not in `examples/`)
4. Run `claudesprint init --spec YOUR_SPEC.md` to generate a sprint

## Spec Structure

A good spec includes:
- **Purpose** - What problem this solves
- **Constraints** - What NOT to do
- **Deliverables** - High-level outcomes
- **Tech Choices** - Technology decisions
- **Work Plan** - Detailed tasks grouped by phase
- **Acceptance Checklist** - Testable success criteria
