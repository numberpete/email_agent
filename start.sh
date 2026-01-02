#!/bin/bash

# EMaiL Assist - Startup Script
# This script sets up the environment and starts the Streamlit UI

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   EMaiL Assist - Startup Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ----------------------------
# 1) Set up virtual environment
# ----------------------------
echo -e "${YELLOW}[1/5] Checking virtual environment...${NC}"

VENV_DIR=".venv"

# Check if we're already in a virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    # Check if venv exists
    if [[ ! -d "$VENV_DIR" ]]; then
        echo -e "  Creating virtual environment with Python 3.12..."
        
        # Check if python3.12 is available
        if command -v python3.12 &> /dev/null; then
            python3.12 -m venv "$VENV_DIR"
        elif command -v python3 &> /dev/null; then
            # Check python3 version
            PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            if [[ "$PYTHON_VERSION" == "3.12" ]]; then
                python3 -m venv "$VENV_DIR"
            else
                echo -e "${RED}  Error: Python 3.12 is required but found Python $PYTHON_VERSION${NC}"
                echo -e "${RED}  Please install Python 3.12 and try again.${NC}"
                exit 1
            fi
        else
            echo -e "${RED}  Error: Python 3 not found. Please install Python 3.12.${NC}"
            exit 1
        fi
        
        echo -e "${GREEN}  Virtual environment created.${NC}"
    else
        echo -e "  Virtual environment already exists."
    fi
    
    # Activate virtual environment
    echo -e "  Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    echo -e "${GREEN}  Virtual environment activated.${NC}"
else
    echo -e "${GREEN}  Already running in virtual environment: $VIRTUAL_ENV${NC}"
fi

# Install dependencies if requirements.txt exists and packages aren't installed
if [[ -f "requirements.txt" ]]; then
    echo -e "  Checking dependencies..."
    if ! pip show streamlit &> /dev/null; then
        echo -e "  Installing dependencies from requirements.txt..."
        pip install -r requirements.txt --quiet
        echo -e "${GREEN}  Dependencies installed.${NC}"
    else
        echo -e "  Dependencies already installed."
    fi
fi

# ----------------------------
# 2) direnv allow
# ----------------------------
echo ""
echo -e "${YELLOW}[2/5] Setting up direnv...${NC}"

if command -v direnv &> /dev/null; then
    if [[ -f ".envrc" ]]; then
        direnv allow . 2>/dev/null || true
        echo -e "${GREEN}  direnv configured.${NC}"
    else
        echo -e "  No .envrc file found, skipping direnv setup."
    fi
else
    echo -e "  direnv not installed, skipping. (This is optional)"
fi

# ----------------------------
# 3 & 4) Check environment variables
# ----------------------------
echo ""
echo -e "${YELLOW}[3/5] Checking environment variables...${NC}"

MISSING_VARS=()

# Check OPENAI_API_KEY
if [[ -z "$OPENAI_API_KEY" ]]; then
    MISSING_VARS+=("OPENAI_API_KEY")
else
    echo -e "  ${GREEN}✓${NC} OPENAI_API_KEY is set"
fi

# Check ANTHROPIC_API_KEY
if [[ -z "$ANTHROPIC_API_KEY" ]]; then
    MISSING_VARS+=("ANTHROPIC_API_KEY")
else
    echo -e "  ${GREEN}✓${NC} ANTHROPIC_API_KEY is set"
fi

# Check SECRET_SALT - create if missing
if [[ -z "$SECRET_SALT" ]]; then
    echo -e "  ${YELLOW}!${NC} SECRET_SALT not set, generating random value..."
    export SECRET_SALT=$(openssl rand -hex 32 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)
    echo -e "  ${GREEN}✓${NC} SECRET_SALT generated"
    
    # Optionally save to .env file
    if [[ -f ".env" ]]; then
        if ! grep -q "SECRET_SALT" .env; then
            echo "SECRET_SALT=$SECRET_SALT" >> .env
            echo -e "  ${GREEN}✓${NC} SECRET_SALT saved to .env file"
        fi
    fi
else
    echo -e "  ${GREEN}✓${NC} SECRET_SALT is set"
fi

# If critical variables are missing, exit with error
if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  ERROR: Missing required environment variables${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    for var in "${MISSING_VARS[@]}"; do
        echo -e "${RED}  • $var${NC}"
    done
    echo ""
    echo -e "Please set these variables before running the application:"
    echo ""
    echo -e "  ${BLUE}export OPENAI_API_KEY='your-openai-api-key'${NC}"
    echo -e "  ${BLUE}export ANTHROPIC_API_KEY='your-anthropic-api-key'${NC}"
    echo ""
    echo -e "Or create a .env file with these values."
    exit 1
fi

echo -e "${GREEN}  All required environment variables are set.${NC}"

# ----------------------------
# Load .env file if it exists
# ----------------------------
echo ""
echo -e "${YELLOW}[4/5] Loading environment file...${NC}"

if [[ -f ".env" ]]; then
    echo -e "  Loading .env file..."
    set -a
    source .env
    set +a
    echo -e "${GREEN}  Environment file loaded.${NC}"
else
    echo -e "  No .env file found, using existing environment."
fi

# ----------------------------
# 5) Start Streamlit UI
# ----------------------------
echo ""
echo -e "${YELLOW}[5/5] Starting EMaiL Assist UI...${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Application starting...${NC}"
echo -e "${GREEN}  Open your browser to the URL below${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Set PYTHONPATH to project root so imports work correctly
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Start Streamlit
exec streamlit run src/ui/app.py \
    --server.headless=true \
    --browser.gatherUsageStats=false \
    --theme.primaryColor="#8B4557" \
    --theme.backgroundColor="#FFFFFF" \
    --theme.secondaryBackgroundColor="#FAF5F7" \
    --theme.textColor="#4A3540"