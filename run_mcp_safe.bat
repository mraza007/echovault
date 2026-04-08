@echo off
REM Launcher for echovault MCP TCP server with port check

set MEMORY_HOME=C:\Git\.memory
set PYTHONPATH=C:\Git\MCP\echovault\src

REM Check if port 8767 is already in use
powershell -Command "try { $conn = Get-NetTCPConnection -LocalPort 8767 -ErrorAction Stop; exit 0 } catch { exit 1 }"
if %ERRORLEVEL% == 0 (
    echo Port 8767 already in use, TCP server running
) else (
    echo Starting TCP server...
    start /B "" "C:\Git\MCP\echovault\.venv\Scripts\python.exe" "C:\Git\MCP\echovault\mcp_tcp_server.py" >nul 2>&1
    timeout /t 3 /nobreak >nul
)

REM Bridge stdio to TCP
"C:\Git\MCP\echovault\.venv\Scripts\python.exe" "C:\Git\MCP\echovault\mcp_bridge.py"
