#!/bin/bash
# browser-guard.sh - Safeguards for browser automation
#
# This PreToolUse hook runs before agent-browser skill calls to:
# 1. Kill orphan browser/chromium processes
# 2. Check available disk space
# 3. Prevent runaway browser sessions

set +e  # Don't exit on errors

# Read JSON input from stdin
INPUT=$(cat)

# Extract the skill being called (for Skill tool)
SKILL=$(node -e "
    try {
        const d = JSON.parse(process.argv[1]);
        process.stdout.write(d.tool_input?.skill || '');
    } catch(e) { process.stdout.write(''); }
" "$INPUT" 2>/dev/null)

# Only proceed if this is an agent-browser skill call
if [ "$SKILL" != "agent-browser" ]; then
    exit 0
fi

# Kill orphan browser processes (chromium, chrome, playwright)
# This prevents zombie browsers from piling up
cleanup_browsers() {
    # Find and kill headless chrome/chromium processes older than 30 minutes
    pkill -f "chromium.*--headless" 2>/dev/null || true
    pkill -f "chrome.*--headless" 2>/dev/null || true

    # Kill any playwright browser server processes that are orphaned
    pkill -f "playwright.*browserServer" 2>/dev/null || true
}

# Check disk space (need at least 500MB for browser cache/screenshots)
check_disk_space() {
    local available_kb=$(df -k . 2>/dev/null | tail -1 | awk '{print $4}')
    local min_required_kb=512000  # 500MB

    if [ -n "$available_kb" ] && [ "$available_kb" -lt "$min_required_kb" ] 2>/dev/null; then
        echo "BLOCKED: Low disk space (${available_kb}KB available, need ${min_required_kb}KB). Free up space before browser automation." >&2
        exit 2
    fi
}

# Check memory (browsers are memory hungry)
check_memory() {
    local available_mb=$(free -m 2>/dev/null | awk '/^Mem:/{print $7}')
    local min_required_mb=256

    if [ -n "$available_mb" ] && [ "$available_mb" -lt "$min_required_mb" ] 2>/dev/null; then
        echo "WARNING: Low memory (${available_mb}MB available). Browser may be slow." >&2
        # Don't block, just warn - let it try
    fi
}

# Run safeguards
cleanup_browsers
check_disk_space
check_memory

# Allow the command
exit 0
