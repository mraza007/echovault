@echo off
REM DEV launcher with custom MEMORY_HOME

set MEMORY_HOME=C:\Git\.memory.dev
set PYTHONPATH=C:\Git\MCP\echovault\src

"C:\Git\MCP\echovault\.venv\Scripts\python.exe" %*
