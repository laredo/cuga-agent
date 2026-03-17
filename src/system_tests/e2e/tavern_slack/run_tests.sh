#!/usr/bin/env bash
# Run Slack integration tests
# Usage: ./run_tests.sh [pytest args]
# Example: ./run_tests.sh -m "slack and not multi_channel"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env if present
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Check that the test API server is running
if ! curl -sf http://localhost:5555/health > /dev/null 2>&1; then
    echo "ERROR: Test API server is not running on port 5555."
    echo "Start it with: uv run python test_api_server.py"
    exit 1
fi

echo "Test API server is up. Running tests..."
uv run pytest specs/ -v "$@"
