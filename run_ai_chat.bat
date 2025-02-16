@echo off
title AI Chat App Setup
cd /d "%~dp0"

:: Check if venv exists, if not, create it
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Upgrade pip & install dependencies
echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

:: Ensure llama-cpp-python works in venv
set PATH=%CD%\venv\Lib\site-packages\llama_cpp;%PATH%

:: Run the AI Chat app
echo Launching AI Chat...
python ai_chat_ui.py

pause
