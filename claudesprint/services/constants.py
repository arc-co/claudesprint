"""Constants for ClaudeSprint services."""

__all__ = ["PROMPTS_README_CONTENT"]

# Content for the prompts README file
PROMPTS_README_CONTENT = """# Prompt Overrides

This directory allows you to customize ClaudeSprint prompts for your project.

## How It Works

To override a built-in prompt, create a file with the same name in this directory.
ClaudeSprint checks this directory first before falling back to built-in prompts.

## Available Prompts

- `PROMPT_init.xml.j2` - Sprint initialization from spec
- `PROMPT_plan.xml.j2` - Planning mode
- `PROMPT_select-issue.xml.j2` - Issue selection step
- `PROMPT_read-docs.xml.j2` - Documentation reading step
- `PROMPT_implement.xml.j2` - Implementation step
- `PROMPT_write-tests.xml.j2` - Test writing step
- `PROMPT_run-tests.xml.j2` - Test execution step
- `PROMPT_fix-tests.xml.j2` - Test fixing step
- `PROMPT_browser-validation.xml.j2` - Browser QA step
- `PROMPT_code-review.xml.j2` - Code review step
- `PROMPT_fix-code-review-issues.xml.j2` - Code review fixes
- `PROMPT_update-docs.xml.j2` - Documentation updates
- `PROMPT_stage-changes.xml.j2` - Stage changes step
- `PROMPT_commit-changes.xml.j2` - Commit changes step

## Example

To customize the implementation prompt:

1. Copy the built-in prompt (or create from scratch)
2. Save as `.claudesprint/prompts/PROMPT_implement.xml.j2`
3. ClaudeSprint will use your version instead

## Notes

- Keep the same structure and required sections
- Test changes with a single issue before using in production
- You can delete override files to revert to built-in behavior
"""
