"""Constants for ClaudeSprint services."""

# Content for the prompts README file
PROMPTS_README_CONTENT = """# Prompt Overrides

This directory allows you to customize ClaudeSprint prompts for your project.

## How It Works

To override a built-in prompt, create a file with the same name in this directory.
ClaudeSprint checks this directory first before falling back to built-in prompts.

## Available Prompts

- `PROMPT_init.md` - Sprint initialization from spec
- `PROMPT_plan.md` - Planning mode
- `PROMPT_implement.md` - Implementation step
- `PROMPT_write-tests.md` - Test writing step
- `PROMPT_run-tests.md` - Test execution step
- `PROMPT_fix-tests.md` - Test fixing step
- `PROMPT_browser-validation.md` - Browser QA step
- `PROMPT_code-review.md` - Code review step
- `PROMPT_fix-code-review-issues.md` - Code review fixes
- `PROMPT_update-docs.md` - Documentation updates

## Example

To customize the implementation prompt:

1. Copy the built-in prompt (or create from scratch)
2. Save as `.claudesprint/prompts/PROMPT_implement.md`
3. ClaudeSprint will use your version instead

## Notes

- Keep the same structure and required sections
- Test changes with a single issue before using in production
- You can delete override files to revert to built-in behavior
"""
