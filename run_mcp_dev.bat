@echo off
REM DEV MCP server launcher with custom MEMORY_HOME

set MEMORY_HOME=C:\Git\.memory.dev
set PYTHONPATH=C:\Git\MCP\echovault\src

REM Kill any existing TCP server
powershell -Command "Get-Process | Where-Object {$_.ProcessName -eq 'python' -and $_.CommandLine -like '*mcp_tcp_server*'} | Stop-Process -Force 2>$null"

REM Start TCP server in background
start /B "" "C:\Git\MCP\echovault\.venv\Scripts\python.exe" "C:\Git\MCP\echovault\mcp_tcp_server.py" >nul 2>&1

REM Wait for server to start
timeout /t 3 /nobreak >nul

REM Run bridge (stdio <-> TCP)
"C:\Git\MCP\echovault\.venv\Scripts\python.exe" "C:\Git\MCP\echovault\mcp_bridge.py"
