#!/bin/bash
# Development environment initialization script for TextBook Exchange MVP
# Run from project root: ./.claude/claudesprint/scripts/init.sh

set -e

echo "=== TextBook Exchange MVP - Development Setup ==="

# Check Node.js version
echo "Checking Node.js..."
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed"
    exit 1
fi
echo "Node.js version: $(node --version)"

# Install npm dependencies
if [ -f "package.json" ]; then
    echo ""
    echo "Installing npm dependencies..."
    npm install
else
    echo ""
    echo "Warning: package.json not found. Run setup-001 issue first."
fi

# Create data directory for SQLite database
echo ""
echo "Ensuring data directory exists..."
mkdir -p data

# Run database migrations if package.json exists and has db:migrate script
if [ -f "package.json" ] && grep -q '"db:migrate"' package.json; then
    echo ""
    echo "Running database migrations..."
    npm run db:migrate
else
    echo ""
    echo "Skipping migrations (db:migrate script not configured yet)"
fi

# Start development server
echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the development server:"
echo "  npm run dev"
echo ""
echo "The server will be available at http://localhost:3000"
