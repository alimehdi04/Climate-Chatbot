#!/bin/bash
# run_production.sh

# Get the directory where this script lives (the project root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure log directory exists
mkdir -p /var/log/climate-rag

# Activate the virtual environment relative to project root
source "$SCRIPT_DIR/.venv/bin/activate"

# Move into the project directory so relative paths in config work
cd "$SCRIPT_DIR"

# Start Gunicorn using the config file
exec gunicorn "app:create_app()" \
    --config gunicorn.conf.py \
    --env FLASK_ENV=production