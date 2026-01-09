#!/bin/bash
# Start script for Janet Mesh Server
# This ensures we use the correct Python interpreter

# Try to find the best Python interpreter
if command -v /opt/homebrew/bin/python3 &> /dev/null; then
    PYTHON=/opt/homebrew/bin/python3
elif command -v /usr/local/bin/python3 &> /dev/null; then
    PYTHON=/usr/local/bin/python3
elif command -v python3 &> /dev/null; then
    PYTHON=python3
else
    echo "Error: python3 not found"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the server
cd "$SCRIPT_DIR"
exec "$PYTHON" server/run.py "$@"
