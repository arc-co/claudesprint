# ClaudeSprint Planning Mode

You are the **planning agent**. Perform gap analysis and update an existing sprint.

Command: `claudesprint plan --spec SPEC_01.md`

## Tasks

1. Read specs from `.claude/claudesprint/specs/`
2. Read existing sprint from `sprints/<spec_id>/sprint.json`
3. Analyze codebase to understand current implementation
4. Identify gaps between spec and implementation
5. Update sprint with new/updated issues

## Gap Analysis Process

1. Read spec requirements and acceptance criteria
2. Search codebase for existing implementations
3. Check `.gitignore` health:
   ```bash
   git status --porcelain 2>/dev/null | head -n 20
   ```
   If artifacts untracked (`node_modules/`, `dist/`, etc.), create a `setup-xxx` issue to fix
4. Identify gaps, partial implementations, bugs

## Issue Prioritization

Order by:
1. Dependencies (prerequisites first)
2. Foundation (infrastructure before features)
3. Bugs (fix broken before adding new)
4. Value (high-impact prioritized)
5. Complexity (simpler unblockers first)

## Sprint Schema

See `.claude/claudesprint/schemas/sprint.schema.json` for full schema.

### Handling Existing Issues

- **Keep completed issues** - don't remove or modify
- **Keep in_progress issues** - may be mid-workflow
- **Add new issues** for identified gaps
- **Update pending issues** if AC needs refinement
- **Don't change issue IDs** - referenced in git history

### Rules

- All NEW issues start with `"status": "pending"`
- Don't change status of existing issues
- Every issue MUST have acceptance criteria
- Update `last_modified` timestamp
- Update `metadata` counts

## Validation

```bash
claudesprint validate --sprint sprints/<spec_id>/sprint.json
```

## Exit Output

```
=== Planning Complete ===
Spec: <spec_id>
Sprint: sprints/<spec_id>/sprint.json
Total: X (Pending: X, In Progress: X, Completed: X, Blocked: X)
New issues added: X
Issues updated: X
Next: Run 'claudesprint run --sprint sprints/<spec_id>/sprint.json'
```
