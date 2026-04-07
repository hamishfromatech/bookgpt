#!/bin/bash

# BookGPT Quick Start Script
# Auto-configures environment, creates venv, and starts the application

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

VENV_DIR="venv"
PYTHON_CMD=""

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}       BookGPT Quick Start${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# Function to install Python on macOS
install_python_macos() {
    echo -e "${BLUE}Installing Python on macOS...${NC}"
    if command -v brew &> /dev/null; then
        brew install python@3.11
        echo -e "${GREEN}✓ Python installed via Homebrew${NC}"
    else
        echo -e "${YELLOW}Homebrew not found. Installing via official installer...${NC}"
        echo "Please download and run the installer from:"
        echo "  https://www.python.org/downloads/macos/"
        echo ""
        read -p "Press Enter after installing Python, or Ctrl+C to cancel..."
    fi
}

# Function to install Python on Linux
install_python_linux() {
    echo -e "${BLUE}Installing Python on Linux...${NC}"
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv
        echo -e "${GREEN}✓ Python installed via apt${NC}"
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y python3 python3-pip python3-virtualenv
        echo -e "${GREEN}✓ Python installed via dnf${NC}"
    elif command -v yum &> /dev/null; then
        sudo yum install -y python3 python3-pip python3-virtualenv
        echo -e "${GREEN}✓ Python installed via yum${NC}"
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm python python-pip
        echo -e "${GREEN}✓ Python installed via pacman${NC}"
    elif command -v zypper &> /dev/null; then
        sudo zypper install -y python3 python3-pip python3-virtualenv
        echo -e "${GREEN}✓ Python installed via zypper${NC}"
    else
        echo -e "${YELLOW}Unknown package manager. Please install Python 3.8+ manually:${NC}"
        echo "  https://www.python.org/downloads/"
        echo ""
        read -p "Press Enter after installing Python, or Ctrl+C to cancel..."
    fi
}

# Function to install Python on Windows (WSL)
install_python_wsl() {
    echo -e "${YELLOW}Running in WSL. Python installation depends on your Linux distro.${NC}"
    install_python_linux
}

# Check if Python is installed
find_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD=python3
        return 0
    elif command -v python &> /dev/null; then
        PYTHON_CMD=python
        return 0
    fi
    return 1
}

# Main Python check and install
if ! find_python; then
    echo -e "${RED}Python is not installed or not in PATH${NC}"
    echo ""

    # Detect OS and offer to install
    OS="$(uname -s)"

    case "$OS" in
        Darwin)
            echo -e "${YELLOW}Detected macOS${NC}"
            read -p "Would you like to install Python via Homebrew? (y/n): " install_choice
            if [ "$install_choice" = "y" ] || [ "$install_choice" = "Y" ]; then
                install_python_macos
            else
                echo "Please install Python 3.8+ from https://www.python.org/downloads/"
                exit 1
            fi
            ;;
        Linux)
            # Check if running in WSL
            if grep -qi microsoft /proc/version 2>/dev/null; then
                echo -e "${YELLOW}Detected WSL (Windows Subsystem for Linux)${NC}"
                install_python_wsl
            else
                echo -e "${YELLOW}Detected Linux${NC}"
                read -p "Would you like to install Python using your package manager? (y/n): " install_choice
                if [ "$install_choice" = "y" ] || [ "$install_choice" = "Y" ]; then
                    install_python_linux
                else
                    echo "Please install Python 3.8+ from https://www.python.org/downloads/"
                    exit 1
                fi
            fi
            ;;
        *)
            echo -e "${YELLOW}Detected: $OS${NC}"
            echo "Please install Python 3.8+ from https://www.python.org/downloads/"
            exit 1
            ;;
    esac

    # Re-check for Python after installation
    if ! find_python; then
        echo -e "${RED}Python still not found. Please install manually and re-run this script.${NC}"
        exit 1
    fi
fi

# Verify Python version
PYTHON_VERSION=$(${PYTHON_CMD} --version 2>&1)
echo -e "${GREEN}✓ Python found: ${PYTHON_VERSION}${NC}"

# Check Python version is 3.8+
PYTHON_VERSION_NUM=$(${PYTHON_CMD} -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')")
if [ "$PYTHON_VERSION_NUM" -lt 38 ]; then
    echo -e "${RED}Error: Python 3.8 or higher is required (found ${PYTHON_VERSION})${NC}"
    exit 1
fi
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${BLUE}Creating virtual environment...${NC}"
    ${PYTHON_CMD} -m venv $VENV_DIR
    echo -e "${GREEN}✓ Virtual environment created at ./${VENV_DIR}${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi
echo ""

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source "${VENV_DIR}/bin/activate"
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Upgrade pip
echo -e "${BLUE}Ensuring pip is up to date...${NC}"
pip install --upgrade pip --quiet

# Check if .env exists, create from .env.example if not
if [ ! -f .env ]; then
    echo -e "${BLUE}Creating .env file from template...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env file${NC}"
    else
        echo -e "${YELLOW}Warning: .env.example not found, creating default .env${NC}"
        cat > .env << EOF
# Flask Configuration
FLASK_SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p)
FLASK_DEBUG=true
PORT=6748

# OpenAI / LLM Configuration (will be updated below)
OPENAI_API_KEY=
LLM_MODEL=

# Stripe / Billing Configuration
STRIPE_ENABLED=false

# Application Domain
DOMAIN=http://localhost:6748
EOF
        echo -e "${GREEN}✓ Created default .env file${NC}"
    fi
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi
echo ""

# Wizard: Ask for AI Provider
echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}       AI Provider Setup${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""
echo "Which AI provider would you like to use?"
echo ""
echo "  1) OpenAI (cloud API - requires API key)"
echo "  2) Ollama (local LLM - free, runs on your machine)"
echo ""

while true; do
    read -p "Enter your choice (1 or 2): " provider_choice
    case $provider_choice in
        1)
            echo ""
            echo -e "${BLUE}You selected: OpenAI${NC}"
            echo ""
            read -p "Enter your OpenAI API key (sk-...): " openai_key
            if [ -z "$openai_key" ]; then
                echo -e "${RED}Error: API key cannot be empty${NC}"
                continue
            fi
            read -p "Enter model name (default: gpt-4o): " openai_model
            openai_model=${openai_model:-gpt-4o}

            # Update .env for OpenAI
            sed -i.bak "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${openai_key}|" .env
            sed -i.bak "s|^# OPENAI_BASE_URL=.*|# OPENAI_BASE_URL=http://localhost:11434/v1  # Uncomment for Ollama|" .env
            sed -i.bak "s|^# LLM_MODEL=.*|LLM_MODEL=${openai_model}|" .env
            rm -f .env.bak 2>/dev/null || true

            echo -e "${GREEN}✓ Configured for OpenAI with model: ${openai_model}${NC}"
            break
            ;;
        2)
            echo ""
            echo -e "${BLUE}You selected: Ollama${NC}"
            echo ""
            echo "Ollama runs locally on your machine. Make sure you have Ollama installed:"
            echo "  - macOS/Linux: curl -fsSL https://ollama.com/install.sh | sh"
            echo "  - Windows: Download from https://ollama.com/download"
            echo ""
            read -p "Enter the Ollama model name (default: llama3.1): " ollama_model
            ollama_model=${ollama_model:-llama3.1}

            # Update .env for Ollama
            sed -i.bak "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=ollama-local|" .env
            sed -i.bak "s|^# OPENAI_BASE_URL=.*|OPENAI_BASE_URL=http://localhost:11434/v1|" .env
            sed -i.bak "s|^# LLM_MODEL=.*|LLM_MODEL=${ollama_model}|" .env
            rm -f .env.bak 2>/dev/null || true

            echo -e "${GREEN}✓ Configured for Ollama with model: ${ollama_model}${NC}"
            echo -e "${YELLOW}Note: Make sure to pull the model first: ollama pull ${ollama_model}${NC}"
            break
            ;;
        *)
            echo -e "${RED}Invalid choice. Please enter 1 or 2.${NC}"
            ;;
    esac
done
echo ""

# Generate a random secret key if still using placeholder
if grep -q "your-secret-key-change-in-production" .env; then
    secret_key=$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p)
    sed -i.bak "s|FLASK_SECRET_KEY=.*|FLASK_SECRET_KEY=${secret_key}|" .env
    rm -f .env.bak 2>/dev/null || true
    echo -e "${GREEN}✓ Generated secure Flask secret key${NC}"
fi
echo ""

# Install dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
if [ -f requirements.txt ]; then
    pip install -r requirements.txt --quiet
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${RED}Error: requirements.txt not found${NC}"
    exit 1
fi
echo ""

# Start the application
echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}       Starting BookGPT${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""
echo -e "${GREEN}BookGPT will be available at: http://localhost:6748${NC}"
echo ""
echo -e "${YELLOW}Default login credentials:${NC}"
echo -e "  Username: user"
echo -e "  Password: password"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

python app.py
