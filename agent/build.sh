#!/bin/bash
# A simple script to build the agent executable

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

# Install dependencies
pip install -r requirements.txt

# Build the executable
pyinstaller --onefile --name live-interpreter-agent agent.py

# Deactivate virtual environment
if [ -d ".venv" ]; then
  deactivate
fi

echo "Build complete. Executable is in the 'dist' directory."
