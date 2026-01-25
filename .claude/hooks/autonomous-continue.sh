#!/bin/bash
# autonomous-continue.sh - Keep Claude working until step is complete
#
# This Stop hook verifies Claude actually completed its step by checking
# if current_issue.json was updated with a new step.
#
# Returns decision: "block" with reason if Claude should continue
# Returns nothing (exit 0) if Claude can stop

# Don't use set -e - we want to handle errors gracefully
set +e

# Use CLAUDE_PROJECT_DIR if available, otherwise calculate
if [ -n "$CLAUDE_PROJECT_DIR" ]; then
    PROJECT_DIR="$CLAUDE_PROJECT_DIR"
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
fi

CURRENT_ISSUE_FILE="$PROJECT_DIR/.claude/claudesprint/project/current_issue.json"
STEP_MARKER="$PROJECT_DIR/.claude/claudesprint/project/.current_step"

# Read hook input
INPUT=$(cat)

# Check if stop hook is already active (prevent infinite loops)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)

if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
    # Already continuing from a stop hook - allow stop to prevent infinite loop
    exit 0
fi

# Check if we're in a loop.sh managed session (step marker exists)
if [ ! -f "$STEP_MARKER" ]; then
    # Not a managed session, allow stop (might be interactive use)
    exit 0
fi

STARTING_STEP=$(cat "$STEP_MARKER" 2>/dev/null | tr -d '\n')

if [ -z "$STARTING_STEP" ]; then
    # No starting step recorded, allow stop
    exit 0
fi

# Check if current_issue.json exists
if [ ! -f "$CURRENT_ISSUE_FILE" ]; then
    # No current_issue file - this is a problem, but let loop.sh handle it
    exit 0
fi

# Get current step and retry_count from current_issue.json
CURRENT_STEP=$(jq -r '.step // ""' "$CURRENT_ISSUE_FILE" 2>/dev/null)
RETRY_COUNT=$(jq -r '.retry_count // 0' "$CURRENT_ISSUE_FILE" 2>/dev/null)

# If workflow is complete, allow stop
if [ "$CURRENT_STEP" = "workflow-complete" ]; then
    exit 0
fi

# If retry count is too high, allow stop (let loop.sh handle the failure)
MAX_RETRY=${CLAUDESPRINT_MAX_RETRY:-5}
if [ "$RETRY_COUNT" -ge "$MAX_RETRY" ] 2>/dev/null; then
    exit 0
fi

# Check if step advanced
if [ "$STARTING_STEP" = "$CURRENT_STEP" ]; then
    # Step hasn't changed - Claude didn't complete the step
    cat << EOF
{
  "decision": "block",
  "reason": "You have not completed this step yet. The step is still '$CURRENT_STEP'. You must: 1) Complete the work for this step, 2) Update current_issue.json with the NEXT step, 3) Run claudesprint validate. Do not stop until current_issue.json shows a different step."
}
EOF
    exit 0
fi

# Step advanced - Claude completed its work
# Clean up marker (optional, loop.sh will overwrite anyway)
rm -f "$STEP_MARKER" 2>/dev/null

exit 0
