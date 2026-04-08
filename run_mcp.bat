@echo off
set PYTHONDONTWRITEBYTECODE=1
set PYTHONUNBUFFERED=1
set PYTHONPATH=c:\Git\MCP\echovault\src;c:\Git\MCP\echovault\.venv\Lib\site-packages
set PATH=c:\Git\MCP\echovault\.venv\Lib\site-packages\pywin32_system32;%PATH%
c:\Git\MCP\echovault\.venv\Scripts\python.exe c:\Git\MCP\echovault\run_mcp.py 2>nul
