#!/bin/bash
# server-guard.sh - Prevent multiple server instances from being spawned
#
# This PreToolUse hook checks if a dev server is already running before
# allowing commands that would start another one.

set +e  # Don't exit on errors

# Read JSON input from stdin
INPUT=$(cat)

# Extract the command being run
COMMAND=$(node -e "
    try {
        const d = JSON.parse(process.argv[1]);
        process.stdout.write(d.tool_input?.command || '');
    } catch(e) { process.stdout.write(''); }
" "$INPUT" 2>/dev/null)

# If we couldn't extract command, allow (fail open)
if [ -z "$COMMAND" ]; then
    exit 0
fi

# Patterns that indicate server startup commands
SERVER_PATTERNS=(
    "npm run dev"
    "npm start"
    "npm run start"
    "npx .* dev"
    "node.*server"
    "tsx.*server"
    "ts-node.*server"
    "pnpm dev"
    "pnpm start"
    "yarn dev"
    "yarn start"
)

# Patterns that indicate watch/interactive commands (these run forever)
WATCH_PATTERNS=(
    "npm run.*watch"
    "npm test.*--watch"
    "jest.*--watch"
    "vitest.*--watch"
    "tsc.*--watch"
    "nodemon"
    "npm run.*:watch"
)

# Check if command is a watch/interactive command
IS_WATCH_COMMAND=false
for pattern in "${WATCH_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qE "$pattern"; then
        IS_WATCH_COMMAND=true
        break
    fi
done

if [ "$IS_WATCH_COMMAND" = true ]; then
    echo "BLOCKED: Watch/interactive commands are not allowed in autonomous mode: $COMMAND" >&2
    echo "Use non-watch variants instead (e.g., 'npm test' instead of 'npm test --watch')" >&2
    exit 2
fi

# Patterns for interactive git commands
INTERACTIVE_GIT_PATTERNS=(
    "git add -i"
    "git add --interactive"
    "git rebase -i"
    "git rebase --interactive"
    "git add -p"
    "git add --patch"
    "git stash.*-p"
    "git stash.*--patch"
)

# Check for interactive git commands
for pattern in "${INTERACTIVE_GIT_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qE "$pattern"; then
        echo "BLOCKED: Interactive git commands are not allowed in autonomous mode: $COMMAND" >&2
        exit 2
    fi
done

# Check if the command matches any server startup pattern
IS_SERVER_COMMAND=false
for pattern in "${SERVER_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qE "$pattern"; then
        IS_SERVER_COMMAND=true
        break
    fi
done

# If not a server command, allow it
if [ "$IS_SERVER_COMMAND" = false ]; then
    exit 0
fi

# Common dev server ports to check
PORTS="3000 3001 5173 5174 8080 8000 4000"

# Use Node.js to check if ports are in use (works everywhere Node is available)
BLOCKED_PORT=$(node -e "
const net = require('net');
const ports = process.argv[1].split(' ').map(Number);

async function checkPort(port) {
    return new Promise((resolve) => {
        const server = net.createServer();
        server.once('error', (err) => {
            if (err.code === 'EADDRINUSE') {
                resolve(port); // Port is in use
            } else {
                resolve(null);
            }
        });
        server.once('listening', () => {
            server.close();
            resolve(null); // Port is free
        });
        server.listen(port);
    });
}

(async () => {
    for (const port of ports) {
        const inUse = await checkPort(port);
        if (inUse) {
            console.log(inUse);
            process.exit(0);
        }
    }
    console.log('');
    process.exit(0);
})();
" "$PORTS" 2>/dev/null)

if [ -n "$BLOCKED_PORT" ]; then
    echo "BLOCKED: Server already running on port $BLOCKED_PORT. Kill it first or use a different port." >&2
    exit 2
fi

# No server running on monitored ports, allow the command
exit 0
