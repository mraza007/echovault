@echo off
set PYTHONDONTWRITEBYTECODE=1
set PYTHONUNBUFFERED=1
set PYTHONWARNINGS=ignore
"%~dp0..\..\.venv\Scripts\python.exe" -m memory.cli %* 2>&1 | findstr /V "Could not find platform independent"
