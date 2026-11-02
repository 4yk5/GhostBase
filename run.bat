@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
title GhostBase - Terminal Database Studio
python main.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo GhostBase stopped with an error or dependencies are missing.
    echo Try running: pip install -r requirements.txt
    pause
)
