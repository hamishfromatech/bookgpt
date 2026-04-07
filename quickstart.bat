@echo off
setlocal enabledelayedexpansion

REM BookGPT Quick Start Script for Windows
REM Auto-configures environment, creates venv, and starts the application

set VENV_DIR=venv
set PYTHON_CMD=python
set PYTHON_INSTALLED=0

echo =====================================
echo        BookGPT Quick Start
echo =====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_CMD=python3
        set PYTHON_INSTALLED=1
    )
) else (
    set PYTHON_INSTALLED=1
)

if "%PYTHON_INSTALLED%"=="0" (
    echo [ERROR] Python is not installed or not in PATH
    echo.
    echo Python 3.8+ is required. Would you like to install it?
    echo.
    set /p "install_python=Install Python now? (y/n): "
    if /i "%install_python%"=="y" (
        echo.
        echo Opening Python download page...
        start https://www.python.org/downloads/
        echo.
        echo [NOTE] After installing Python:
        echo   1. Close this window
        echo   2. Re-run quickstart.bat
        echo.
        pause
        exit /b 1
    ) else (
        echo.
        echo Please install Python 3.8+ from https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
)

for /f "tokens=*" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python found: %PYTHON_VERSION%
echo.

REM Create virtual environment if it doesn't exist
if not exist "%VENV_DIR%" (
    echo [INFO] Creating virtual environment...
    %PYTHON_CMD% -m venv %VENV_DIR%
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        echo Make sure you have Python 3.8+ with venv module installed
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created at .\%VENV_DIR%
) else (
    echo [OK] Virtual environment already exists
)
echo.

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment activated
echo.

REM Upgrade pip
echo [INFO] Ensuring pip is up to date...
python -m pip install --upgrade pip --quiet
echo [OK] pip is up to date
echo.

REM Check if .env exists, create from .env.example if not
if not exist .env (
    echo [INFO] Creating .env file from template...
    if exist .env.example (
        copy .env.example .env >nul
        echo [OK] Created .env file
    ) else (
        echo [WARN] .env.example not found, creating default .env
        echo # Flask Configuration> .env
        echo FLASK_SECRET_KEY=%RANDOM%%RANDOM%%RANDOM%>> .env
        echo FLASK_DEBUG=true>> .env
        echo PORT=6748>> .env
        echo.>> .env
        echo # OpenAI / LLM Configuration (will be updated below)>> .env
        echo OPENAI_API_KEY=placeholder>> .env
        echo LLM_MODEL=placeholder>> .env
        echo.>> .env
        echo # Stripe / Billing Configuration>> .env
        echo STRIPE_ENABLED=false>> .env
        echo.>> .env
        echo # Application Domain>> .env
        echo DOMAIN=http://localhost:6748>> .env
        echo [OK] Created default .env file
    )
) else (
    echo [OK] .env file already exists
)
echo.

REM Wizard: Ask for AI Provider
echo =====================================
echo        AI Provider Setup
echo =====================================
echo.
echo Which AI provider would you like to use?
echo.
echo   1) OpenAI (cloud API - requires API key)
echo   2) Ollama (local LLM - free, runs on your machine)
echo.

:PROVIDER_CHOICE
set /p "provider_choice=Enter your choice (1 or 2): "
if "%provider_choice%"=="1" goto OPENAI_SETUP
if "%provider_choice%"=="2" goto OLLAMA_SETUP
echo [ERROR] Invalid choice. Please enter 1 or 2.
goto PROVIDER_CHOICE

:OPENAI_SETUP
echo.
echo [INFO] You selected: OpenAI
echo.
set /p "openai_key=Enter your OpenAI API key (sk-...): "
if "%openai_key%"=="" (
    echo [ERROR] API key cannot be empty
    goto OPENAI_SETUP
)
set /p "openai_model=Enter model name (default: gpt-4o): "
if "%openai_model%"=="" set openai_model=gpt-4o

REM Update .env for OpenAI using PowerShell
powershell -Command "(Get-Content .env) -replace '^OPENAI_API_KEY=.*', 'OPENAI_API_KEY=%openai_key%' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace '^# OPENAI_BASE_URL=.*', '# OPENAI_BASE_URL=http://localhost:11434/v1  # Uncomment for Ollama' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace '^# LLM_MODEL=.*', 'LLM_MODEL=%openai_model%' | Set-Content .env"

echo [OK] Configured for OpenAI with model: %openai_model%
goto CONFIG_COMPLETE

:OLLAMA_SETUP
echo.
echo [INFO] You selected: Ollama
echo.
echo Ollama runs locally on your machine. Make sure you have Ollama installed:
echo   Download from: https://ollama.com/download
echo.
set /p "ollama_model=Enter the Ollama model name (default: llama3.1): "
if "%ollama_model%"=="" set ollama_model=llama3.1

REM Update .env for Ollama using PowerShell
powershell -Command "(Get-Content .env) -replace '^OPENAI_API_KEY=.*', 'OPENAI_API_KEY=ollama-local' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace '^# OPENAI_BASE_URL=.*', 'OPENAI_BASE_URL=http://localhost:11434/v1' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace '^# LLM_MODEL=.*', 'LLM_MODEL=%ollama_model%' | Set-Content .env"

echo [OK] Configured for Ollama with model: %ollama_model%
echo [NOTE] Make sure to pull the model first: ollama pull %ollama_model%
goto CONFIG_COMPLETE

:CONFIG_COMPLETE
echo.

REM Install dependencies
echo [INFO] Installing dependencies...
if exist requirements.txt (
    python -m pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed
) else (
    echo [ERROR] requirements.txt not found
    pause
    exit /b 1
)
echo.

REM Start the application
echo =====================================
echo        Starting BookGPT
echo =====================================
echo.
echo [OK] BookGPT will be available at: http://localhost:6748
echo.
echo [NOTE] Default login credentials:
echo   Username: user
echo   Password: password
echo.
echo [NOTE] Press Ctrl+C to stop the server
echo.

python app.py
