"""MCP Server wrapper to filter Windows Store Python warnings."""

import os
import sys

# Set up paths BEFORE any imports that might need pywin32
base_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(base_dir, 'src')
venv_packages = os.path.join(base_dir, '.venv', 'Lib', 'site-packages')
pywin32_path = os.path.join(venv_packages, 'pywin32_system32')

# Add to sys.path
sys.path.insert(0, src_path)
sys.path.insert(0, venv_packages)

# Add pywin32 to PATH (must be done before importing pywin32 modules)
if pywin32_path not in os.environ.get('PATH', ''):
    os.environ['PATH'] = pywin32_path + os.pathsep + os.environ.get('PATH', '')

# Suppress Windows Store Python warning
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['PYTHONUNBUFFERED'] = '1'

# Now run the actual MCP server
from memory.cli import main
sys.argv = ['memory', 'mcp']
main()
