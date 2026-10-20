#!/bin/bash
# Career Radar v4.0 - Desktop Launcher
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=================================================="
echo "🎯 Starting Career Radar v4.0 (Enterprise Radar)..."
echo "=================================================="

# Check if server is already running on port 8050
if lsof -Pi :8050 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚡ Career Radar is already running on http://127.0.0.1:8050"
else
    echo "🚀 Launching Career Radar server in background..."
    if [ -f ".venv/bin/python3" ]; then
        nohup .venv/bin/python3 app.py > server.log 2>&1 &
    else
        nohup python3 app.py > server.log 2>&1 &
    fi
    sleep 2
fi

echo "🌐 Opening Dashboard in default browser..."
open "http://127.0.0.1:8050"

echo "✅ Ready! Dashboard opened at http://127.0.0.1:8050"

