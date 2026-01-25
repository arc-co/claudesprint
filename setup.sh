#!/bin/bash
#
# ClaudeSprint Setup Script
# =======================
# Sets up the development environment for the ClaudeSprint workflow system.
#
# Usage:
#   ./setup.sh              # Full setup with virtual environment
#   ./setup.sh --no-venv    # Install without creating a virtual environment
#   ./setup.sh --no-browser # Skip browser automation installation
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
USE_VENV=true
INSTALL_BROWSER=true

for arg in "$@"; do
    case $arg in
        --no-venv)
            USE_VENV=false
            shift
            ;;
        --no-browser)
            INSTALL_BROWSER=false
            shift
            ;;
        --help|-h)
            echo "Usage: ./setup.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --no-venv      Skip virtual environment creation (use system Python)"
            echo "  --no-browser   Skip browser automation installation (agent-browser)"
            echo "  --help, -h     Show this help message"
            exit 0
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  ClaudeSprint Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed.${NC}"
    echo "Please install Python 3.10 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo -e "${RED}Error: Python 3.10 or higher is required (found $PYTHON_VERSION).${NC}"
    exit 1
fi

echo -e "${GREEN}Found Python $PYTHON_VERSION${NC}"

# Create virtual environment if requested
if [ "$USE_VENV" = true ]; then
    echo ""
    echo -e "${YELLOW}Creating virtual environment...${NC}"

    if [ -d ".venv" ]; then
        echo -e "${YELLOW}Virtual environment already exists at .venv${NC}"
        read -p "Do you want to recreate it? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf .venv
            python3 -m venv .venv
            echo -e "${GREEN}Virtual environment recreated.${NC}"
        else
            echo "Using existing virtual environment."
        fi
    else
        python3 -m venv .venv
        echo -e "${GREEN}Virtual environment created at .venv${NC}"
    fi

    # Activate virtual environment
    source .venv/bin/activate
    echo -e "${GREEN}Virtual environment activated.${NC}"
fi

# Upgrade pip
echo ""
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip --quiet
echo -e "${GREEN}pip upgraded.${NC}"

# Install claudesprint package in editable mode
echo ""
echo -e "${YELLOW}Installing ClaudeSprint package...${NC}"
pip install -e ".claude/claudesprint/[dev]" --quiet
echo -e "${GREEN}ClaudeSprint package installed.${NC}"

# Install browser automation (agent-browser)
if [ "$INSTALL_BROWSER" = true ]; then
    echo ""
    echo -e "${YELLOW}Installing agent-browser (browser automation)...${NC}"

    # Check if npm is available
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}Warning: npm is not installed. Skipping agent-browser installation.${NC}"
        echo "To install later: npm install -g agent-browser && agent-browser install"
        INSTALL_BROWSER=false
    else
        # Check if agent-browser is already installed globally
        if command -v agent-browser &> /dev/null; then
            echo -e "${GREEN}agent-browser is already installed globally.${NC}"
        else
            # Warn user about global install
            echo -e "${YELLOW}This will install agent-browser globally (npm install -g).${NC}"
            echo "This may require sudo on some systems and modifies your global npm packages."
            read -p "Continue with global installation? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo -e "${YELLOW}Skipping agent-browser installation.${NC}"
                echo "To install later: npm install -g agent-browser && agent-browser install"
                INSTALL_BROWSER=false
            fi
        fi

        if [ "$INSTALL_BROWSER" = true ]; then
            # Install agent-browser globally via npm
            npm install -g agent-browser --silent 2>/dev/null || npm install -g agent-browser
            echo -e "${GREEN}agent-browser CLI installed.${NC}"

            # Install Chromium browser
            echo -e "${YELLOW}Installing Chromium browser...${NC}"

            # Detect OS and install with appropriate flags
            if [[ "$OSTYPE" == "linux-gnu"* ]]; then
                # Linux: install with system dependencies
                echo -e "${YELLOW}Detected Linux - installing with system dependencies...${NC}"
                agent-browser install --with-deps 2>/dev/null || {
                    echo -e "${YELLOW}Note: System deps installation may require sudo.${NC}"
                    echo "If browser tests fail, run: sudo npx playwright install-deps chromium"
                    agent-browser install
                }
            else
                # macOS/Windows: standard install
                agent-browser install
            fi

            echo -e "${GREEN}Chromium browser installed.${NC}"

            # Quick test to verify installation
            echo ""
            echo -e "${YELLOW}Testing agent-browser installation...${NC}"
            if agent-browser open example.com --headless 2>/dev/null; then
                agent-browser close 2>/dev/null || true
                echo -e "${GREEN}agent-browser is working correctly!${NC}"
            else
                # Try without headless flag
                if timeout 10 agent-browser open example.com 2>/dev/null; then
                    agent-browser close 2>/dev/null || true
                    echo -e "${GREEN}agent-browser is working correctly!${NC}"
                else
                    echo -e "${YELLOW}Warning: agent-browser test failed. It may still work in your environment.${NC}"
                    echo "You can test manually with: agent-browser open example.com"
                fi
            fi
        fi
    fi
fi

# Verify claudesprint installation
echo ""
echo -e "${YELLOW}Verifying ClaudeSprint installation...${NC}"
if command -v claudesprint &> /dev/null; then
    echo -e "${GREEN}ClaudeSprint CLI installed successfully!${NC}"
    claudesprint --help | head -5
else
    # Try with path prefix in case shell hash isn't updated
    if .venv/bin/claudesprint --help &> /dev/null 2>&1; then
        echo -e "${GREEN}ClaudeSprint CLI installed successfully!${NC}"
        echo "(You may need to restart your shell or run 'hash -r' for the command to be available)"
    else
        echo -e "${RED}Warning: claudesprint command not found in PATH.${NC}"
        echo "Try running: source .venv/bin/activate"
    fi
fi

# Print next steps
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Setup complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Next steps:"
echo ""
if [ "$USE_VENV" = true ]; then
    echo "  1. Activate the virtual environment:"
    echo -e "     ${YELLOW}source .venv/bin/activate${NC}"
    echo ""
fi
echo "  2. Verify the installation:"
echo -e "     ${YELLOW}claudesprint status${NC}"
echo ""
echo "  3. Initialize a sprint from a spec:"
echo -e "     ${YELLOW}claudesprint init --spec .claude/claudesprint/specs/YOUR_SPEC.md${NC}"
echo ""
echo "  4. Run the workflow:"
echo -e "     ${YELLOW}claudesprint run --sprint .claude/claudesprint/sprints/YOUR_SPEC/sprint.json${NC}"
echo ""

if [ "$INSTALL_BROWSER" = false ]; then
    echo -e "${YELLOW}Note:${NC} Browser automation (agent-browser) was not installed."
    echo "      To add it later: npm install -g agent-browser && agent-browser install"
    echo ""
fi

echo "For more information, see:"
echo "  - .claude/CLAUDE.md - Project workflow documentation"
echo "  - .claude/claudesprint/README.md - ClaudeSprint CLI documentation"
echo ""
